#!/bin/sh
sudo apt install mysql-client-core-5.7 sysbench

sysbench --test=oltp --mysql-host=$MYSQL_HOST --mysql-user=$MYSQL_USER --mysql-password=$MYSQL_PASSWORD --mysql-table-engine=innodb --oltp-table-size=1000000 --max-time=180 --max-requests=0 prepare

sysbench --num-threads=25 --max-requests=100000 --test=oltp --mysql-host=$MYSQL_HOST --mysql-user=$MYSQL_USER --mysql-password=$MYSQL_PASSWORD --mysql-table-engine=innodb --oltp-table-size=1000000 --max-time=180 --max-requests=0 run