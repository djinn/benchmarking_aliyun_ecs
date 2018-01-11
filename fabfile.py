#!/usr/bin/env fab
from csv import DictReader
from codecs import open as uopen
from json import loads, dumps
from string import ascii_letters, punctuation
from fabric.api import *
from cStringIO import StringIO
from os import urandom
keyFd = DictReader(uopen("/Users/ss/keys/aliyun_key.csv", 'r', encoding='utf-8-sig'))
d = keyFd.next()

env.user ='ubuntu'
env.region = 'ap-southeast-1'
env.key_filename = ['/Users/ss/keys/ralali_production_key.pem']
env.access_key = d['AccessKeyId']
env.access_secret = d['AccessKeySecret']
env.key_pair = 'default_aliyun'
env.instance = 'ecs.n1.small'
env.zone = 'a'
env.imageid = 'ubuntu_16_0402_64_20G_alibase_20171227.vhd'
env.wp_tarball = 'http://wordpress.org/latest.tar.gz'
env.domain = 'test-aliyun.wordpress'
env.dbname = 'test_aliyun_db'


@task
def provision_ecs():
	instance_details = local("aliyuncli ecs CreateInstance --AccessKeyId %s --AccessKeySecret %s --KeyPairName %s --RegionId %s --InstanceType %s --ImageId %s" % \
			(env.access_key, env.access_secret, env.key_pair, env.region, env.instance, env.imageid))
	env.ecs_instance = loads(instance_details)['InstanceId']
	return 


@task 
def apt_install():
	sudo('apt install -y nginx php-cgi mysql-client-5.7 php7.0-mysql php7.0-json php7.0-gd')

@task
def provision_rds():
	instance_details = local("aliyuncli rds CreateDBInstance --AccessKeyId %s --AccessKeySecret %s --RegionId %s --DBName %s --Engine MySQL --EngineVersion 5.7 --DBInstanceClass mysql.n1.micro.1 --DBInstanceStorage 20000 --DBInstanceNetType 2000 --SecurityIPList 0.0.0.0/0 --PayType Pay-As-You-Go" % \
			(env.access_key, env.access_secret, env.region, env.dbname))
	env.ecs_database = loads(instance_details)['InstanceId']
	return 
@task
def provision():
	provision_ecs()
	provision_rds()	
	return


def _check_sudo():
    with settings(warn_only=True):
        result = sudo('pwd')
        if result.failed:
            print "Trying to install sudo. Must be root"
            run('apt-get update && apt-get install -y sudo')


def create_credentials(domain):
    return {
        "user": domain.replace('.', '')[:16],
        "password": urandom(16).encode('hex')[:13],
        "dbname": domain.replace('.', '')[3:18]
    }


def wp_prefix():
    """
    New database prefix for WordPress wp-config.php
    """
    return '"{0}_"'.format(''.join(choice(ascii_letters) for x in range(2)))


def wp_salt():
    """
    Salts for WordPress wp-config.php
    """
    match = r"[\",',\\,\*,\/]"
    charset = re.sub(match, 'x', ascii_letters + punctuation)
    return "'" + ''.join(choice(charset) for x in range(64)) + "'"

@task
def setup_database(credentials):
    """
    Creates mysql database using credentials
    """

    with settings(warn_only=True):
        if sudo('mysqladmin create ' + credentials['dbname']).failed:
            sudo('mysqladmin drop ' + credentials['dbname'])
            sudo('mysqladmin create ' + credentials['dbname'])

    sql = """echo "GRANT ALL PRIVILEGES ON {dbname}.* TO '{user}'@localhost IDENTIFIED BY '{password}';" | mysql"""
    sudo(sql.format(**credentials))

@task
def www(domain):
    """
    Create new www file directory
    """

    with cd("/var/www/"):
        sudo("mkdir " + domain)
        sudo('chown -R www-data:www-data ' + domain)
        sudo('chmod -R g+rw ' + domain)

@task
def nginx():
    """
    Create new PHP NGINX server in /etc/nginx/ with web directory at /var/www
    """
    domain = env.domain
    default_config = """
    server {{
        server_name {1};
        return 301 $scheme://{0}$request_uri;
    }}
    server {{
        server_name {0};
        root /var/www/{0};
        location / {{
            try_files $uri $uri/ /index.php?$args;
        }}
        access_log /var/log/nginx/{0}.access.log;
        error_log /var/log/nginx/{0}.error.log;
    }}
    """
    new_config = default_config.format(domain, domain[4:])

    with cd('/etc/nginx/sites-available/'):
        with settings(warn_only=True):
            if (put(StringIO(new_config), domain, use_sudo=True)).failed:
                pass

    with cd('/etc/nginx/sites-enabled'):
        with settings(warn_only=True):
            if (sudo("ln -s /etc/nginx/sites-available/" + domain)).failed:
                pass

    www(domain)

    sudo('systemctl reload nginx')

@task
def wordpress():
    """
    Installs WordPress, including NGINX config, DB, and wp-config.php
    """
    domain = env.domain
    apt_install()
    credentials = create_credentials(domain)
    wp_config = StringIO()
    match = {
        "user": 'username_here',
        "password": 'password_here',
        "dbname": 'database_name_here',
        "phrase": "'put your unique phrase here'",
        "prefix": "'wp_'"
    }

    nginx()
    # www(domain)
    setup_database(credentials)

    with cd('/var/www/' + domain):
        # clone wordpress
        run('wget %s', env.wp_tarball)
        # checkout latest tag (stable branch in SVN)
        run('tar -zxf %s', env.wp_tarball)
        run('mv wordpress/* .')

        get('wp-config-sample.php', wp_config)
        new_config = wp_config.getvalue()

        for key in match:
            if "phrase" in key:
                new_config = re.sub(match[key], wp_salt, new_config)
            elif "prefix" in key:
                new_config = re.sub(match[key], wp_prefix, new_config)
            else:
                new_config = re.sub(match[key], credentials[key], new_config)

        put(StringIO(new_config), "wp-config.php")