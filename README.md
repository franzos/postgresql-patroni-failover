# PostgreSQL High Availability with Patroni, etcd, and HAProxy

This setup demonstrates transparent PostgreSQL failover using:
- **Patroni**: Manages PostgreSQL replication and automatic failover
- **etcd**: Distributed configuration store for leader election
- **HAProxy**: Load balancer providing transparent failover to applications
- **PgBouncer**: Connection pooler for efficient database connections
- **Monitor**: Python script showing continuous read/write operations

## Architecture

```
Application
    |
    v
PgBouncer (6432: connection pooling)
    |
    v
HAProxy (5432: transparent routing)
    |
    ├── pg1 (PostgreSQL + Patroni)
    └── pg2 (PostgreSQL + Patroni)
         |
         v
    etcd cluster (3 nodes)
```

## Quick Start

1. Start the cluster:

```bash
docker-compose up -d
```

2. Wait for initialization (about 30 seconds):

```bash
docker-compose logs -f pg1 pg2
```

3. View HAProxy statistics:

```
http://localhost:7000
```

4. Watch the monitor:

```bash
docker-compose logs -f monitor
```

The monitor uses a single connection to HAProxy port 5432. HAProxy automatically routes writes to the primary and handles failover transparently.

```bash
pg1      | 2025-08-10 21:34:40,181 INFO: no action. I am (pg1), the leader with the lock
pg2      | 2025-08-10 21:34:40,225 INFO: no action. I am (pg2), a secondary, and following a leader (pg1)

monitor  | [21:34:41] WRITE: ID=2, Data='Test data #2'
monitor  | [21:34:41] READ: Total records=2, Latest: ID=2, Data='Test data #2'
monitor  | [21:34:42] WRITE: ID=3, Data='Test data #3'
monitor  | [21:34:42] READ: Total records=3, Latest: ID=3, Data='Test data #3'
monitor  | [21:34:43] WRITE: ID=4, Data='Test data #4'
monitor  | [21:34:43] READ: Total records=4, Latest: ID=4, Data='Test data #4'
```

## Testing Failover

Check which node is the primary:

```bash
$ docker exec pg2 patronictl -c /etc/patroni.yml list
+ Cluster: postgres-cluster (7537073505429905430) -----+
| Member | Host | Role    | State     | TL | Lag in MB |
+--------+------+---------+-----------+----+-----------+
| pg1    | pg1  | Leader  | running   |  1 |           |
| pg2    | pg2  | Replica | streaming |  1 |         0 |
+--------+------+---------+-----------+----+-----------+
```

Shutdown the primary node (pg1) to trigger failover:

```bash
docker stop pg1
```

Here's what this looks like:

```bash
pg1        | 2025-08-10 21:57:21,333 INFO: no action. I am (pg1), the leader with the lock
pg2        | 2025-08-10 21:57:21,376 INFO: no action. I am (pg2), a secondary, and following a leader (pg1)
pgbouncer  | 2025-08-10 21:57:22.185 UTC [1] LOG C-0x562e437743f0: postgres/postgres@192.168.100.9:60872 login attempt: db=postgres user=postgres tls=no
monitor    | [21:57:22] WRITE: ID=200, Data='Test data #75'
pgbouncer  | 2025-08-10 21:57:22.191 UTC [1] LOG C-0x562e437743f0: postgres/postgres@192.168.100.9:60872 closing because: client close request (age=0s)
pgbouncer  | 2025-08-10 21:57:22.192 UTC [1] LOG C-0x562e437743f0: postgres/postgres@192.168.100.9:60876 login attempt: db=postgres user=postgres tls=no
monitor    | [21:57:22] READ: Total records=169, Latest: ID=200, Data='Test data #75'
pgbouncer  | 2025-08-10 21:57:22.193 UTC [1] LOG C-0x562e437743f0: postgres/postgres@192.168.100.9:60876 closing because: client close request (age=0s)
pgbouncer  | 2025-08-10 21:57:23.195 UTC [1] LOG C-0x562e437743f0: postgres/postgres@192.168.100.9:60880 login attempt: db=postgres user=postgres tls=no
monitor    | [21:57:23] WRITE: ID=201, Data='Test data #76'
pgbouncer  | 2025-08-10 21:57:23.201 UTC [1] LOG C-0x562e437743f0: postgres/postgres@192.168.100.9:60880 closing because: client close request (age=0s)
pgbouncer  | 2025-08-10 21:57:23.202 UTC [1] LOG C-0x562e437743f0: postgres/postgres@192.168.100.9:60886 login attempt: db=postgres user=postgres tls=no
monitor    | [21:57:23] READ: Total records=170, Latest: ID=201, Data='Test data #76'
pgbouncer  | 2025-08-10 21:57:23.203 UTC [1] LOG C-0x562e437743f0: postgres/postgres@192.168.100.9:60886 closing because: client close request (age=0s)
pg2        | 2025-08-10 21:57:23.629 UTC [50] FATAL:  could not receive data from WAL stream: server closed the connection unexpectedly
pg2        | 		This probably means the server terminated abnormally
pg2        | 		before or while processing the request.
pg2        | 2025-08-10 21:57:23.629 UTC [33] LOG:  invalid record length at 0/4015EB0: expected at least 24, got 0
pgbouncer  | 2025-08-10 21:57:23.629 UTC [1] LOG S-0x562e437d94f0: postgres/postgres@192.168.100.7:5432 closing because: server conn crashed? (age=106s)
pg2        | 2025-08-10 21:57:23.635 UTC [230] FATAL:  could not connect to the primary server: connection to server at "pg1" (192.168.100.6), port 5432 failed: Connection refused
pg2        | 		Is the server running on that host and accepting TCP/IP connections?
pg2        | 2025-08-10 21:57:23.635 UTC [33] LOG:  waiting for WAL to become available at 0/4015EC8
pg1 exited with code 137
pgbouncer  | 2025-08-10 21:57:24.204 UTC [1] LOG C-0x562e437743f0: postgres/postgres@192.168.100.9:60898 login attempt: db=postgres user=postgres tls=no
pgbouncer  | 2025-08-10 21:57:24.236 UTC [1] LOG S-0x562e437d94f0: postgres/postgres@192.168.100.7:5432 new connection to server (from 192.168.100.8:59828)
haproxy    | <134>Aug 10 21:57:24 haproxy[8]: Connect from 192.168.100.8:59828 to 192.168.100.7:5432 (postgres_write/TCP)
pg2        | 2025-08-10 21:57:24,880 INFO: no action. I am (pg2), a secondary, and following a leader (pg1)
pg2        | 2025-08-10 21:57:27,830 INFO: no action. I am (pg2), a secondary, and following a leader (pg1)
pg2        | 2025-08-10 21:57:30,830 INFO: no action. I am (pg2), a secondary, and following a leader (pg1)
pg2        | 2025-08-10 21:57:33,834 INFO: no action. I am (pg2), a secondary, and following a leader (pg1)
pg2        | 2025-08-10 21:57:36,830 INFO: no action. I am (pg2), a secondary, and following a leader (pg1)
pgbouncer  | 2025-08-10 21:57:39.244 UTC [1] LOG S-0x562e437d94f0: postgres/postgres@192.168.100.7:5432 closing because: server conn crashed? (age=15s)
pgbouncer  | 2025-08-10 21:57:39.275 UTC [1] LOG S-0x562e437d9720: postgres/postgres@192.168.100.7:5432 new connection to server (from 192.168.100.8:37762)
haproxy    | <134>Aug 10 21:57:39 haproxy[8]: Connect from 192.168.100.8:37762 to 192.168.100.7:5432 (postgres_write/TCP)
pg2        | 2025-08-10 21:57:39,834 INFO: no action. I am (pg2), a secondary, and following a leader (pg1)
haproxy    | [WARNING]  (8) : Server postgres_primary/pg1 is DOWN, reason: Layer4 timeout, check duration: 3003ms. 0 active and 0 backup servers left. 1 sessions active, 0 requeued, 0 remaining in queue.
haproxy    | [ALERT]    (8) : backend 'postgres_primary' has no server available!
haproxy    | <129>Aug 10 21:57:41 haproxy[8]: Server postgres_primary/pg1 is DOWN, reason: Layer4 timeout, check duration: 3003ms. 0 active and 0 backup servers left. 1 sessions active, 0 requeued, 0 remaining in queue.
haproxy    | <128>Aug 10 21:57:41 haproxy[8]: backend postgres_primary has no server available!
pg2        | 2025-08-10 21:57:43,597 WARNING: Request failed to pg1: GET http://pg1:8008/patroni (HTTPConnectionPool(host='pg1', port=8008): Max retries exceeded with url: /patroni (Caused by ConnectTimeoutError(<urllib3.connection.HTTPConnection object at 0x7fe6569076d0>, 'Connection to pg1 timed out. (connect timeout=2)')))
pg2        | 2025-08-10 21:57:43.673 UTC [235] FATAL:  could not connect to the primary server: could not translate host name "pg1" to address: Name or service not known
pg2        | 2025-08-10 21:57:43,740 INFO: promoted self to leader by acquiring session lock
pg2        | server promoting
pg2        | 2025-08-10 21:57:43.742 UTC [33] LOG:  received promote request
pg2        | 2025-08-10 21:57:44,594 INFO: Lock owner: pg2; I am pg2
pg2        | 2025-08-10 21:57:44,708 INFO: updated leader lock during promote
pg2        | 2025-08-10 21:57:47,722 INFO: no action. I am (pg2), the leader with the lock
haproxy    | <133>Aug 10 21:57:47 haproxy[8]: Server postgres_primary/pg2 is UP, reason: Layer7 check passed, code: 200, check duration: 1ms. 1 active and 0 backup servers online. 0 sessions requeued, 0 total in queue.
haproxy    | [WARNING]  (8) : Server postgres_primary/pg2 is UP, reason: Layer7 check passed, code: 200, check duration: 1ms. 1 active and 0 backup servers online. 0 sessions requeued, 0 total in queue.
pg2        | 2025-08-10 21:57:50,639 INFO: no action. I am (pg2), the leader with the lock
pg2        | 2025-08-10 21:57:53,639 INFO: no action. I am (pg2), the leader with the lock
pgbouncer  | 2025-08-10 21:57:54.285 UTC [1] LOG S-0x562e437d9720: postgres/postgres@192.168.100.7:5432 closing because: server conn crashed? (age=15s)
haproxy    | <134>Aug 10 21:57:54 haproxy[8]: Connect from 192.168.100.8:45092 to 192.168.100.7:5432 (postgres_write/TCP)
pgbouncer  | 2025-08-10 21:57:54.493 UTC [1] LOG S-0x562e437d94f0: postgres/postgres@192.168.100.7:5432 new connection to server (from 192.168.100.8:45092)
pg2        | 2025-08-10 21:57:54.504 UTC [265] ERROR:  cannot execute INSERT in a read-only transaction
pg2        | 2025-08-10 21:57:54.504 UTC [265] STATEMENT:  INSERT INTO test_data (data, node_name) VALUES ('Test data #77', 'postgres-cluster') RETURNING id
monitor    | [21:57:54] WRITE ERROR: cannot execute INSERT in a read-only transaction
monitor    | ...
pgbouncer  | 2025-08-10 21:57:54.504 UTC [1] LOG C-0x562e437743f0: postgres/postgres@192.168.100.9:60898 closing because: client close request (age=30s)
pgbouncer  | 2025-08-10 21:57:54.505 UTC [1] LOG C-0x562e437743f0: postgres/postgres@192.168.100.9:51124 login attempt: db=postgres user=postgres tls=no
monitor    | [21:57:54] READ: Total records=984, Latest: ID=1039, Data='Test data #1008'
pgbouncer  | 2025-08-10 21:57:54.507 UTC [1] LOG C-0x562e437743f0: postgres/postgres@192.168.100.9:51124 closing because: client close request (age=0s)
pgbouncer  | 2025-08-10 21:57:55.508 UTC [1] LOG C-0x562e437743f0: postgres/postgres@192.168.100.9:51132 login attempt: db=postgres user=postgres tls=no
pg2        | 2025-08-10 21:57:55.509 UTC [265] ERROR:  cannot execute INSERT in a read-only transaction
pg2        | 2025-08-10 21:57:55.509 UTC [265] STATEMENT:  INSERT INTO test_data (data, node_name) VALUES ('Test data #77', 'postgres-cluster') RETURNING id
monitor    | [21:57:55] WRITE ERROR: cannot execute INSERT in a read-only transaction
monitor    | ...
pgbouncer  | 2025-08-10 21:57:55.510 UTC [1] LOG C-0x562e437743f0: postgres/postgres@192.168.100.9:51132 closing because: client close request (age=0s)
pgbouncer  | 2025-08-10 21:57:55.510 UTC [1] LOG C-0x562e437743f0: postgres/postgres@192.168.100.9:51138 login attempt: db=postgres user=postgres tls=no
monitor    | [21:57:55] READ: Total records=984, Latest: ID=1039, Data='Test data #1008'
pgbouncer  | 2025-08-10 21:57:55.511 UTC [1] LOG C-0x562e437743f0: postgres/postgres@192.168.100.9:51138 closing because: client close request (age=0s)
pgbouncer  | 2025-08-10 21:57:56.512 UTC [1] LOG C-0x562e437743f0: postgres/postgres@192.168.100.9:51146 login attempt: db=postgres user=postgres tls=no
pg2        | 2025-08-10 21:57:56.513 UTC [265] ERROR:  cannot execute INSERT in a read-only transaction
pg2        | 2025-08-10 21:57:56.513 UTC [265] STATEMENT:  INSERT INTO test_data (data, node_name) VALUES ('Test data #77', 'postgres-cluster') RETURNING id
monitor    | [21:57:56] WRITE ERROR: cannot execute INSERT in a read-only transaction
monitor    | ...
pgbouncer  | 2025-08-10 21:57:56.513 UTC [1] LOG C-0x562e437743f0: postgres/postgres@192.168.100.9:51146 closing because: client close request (age=0s)
pgbouncer  | 2025-08-10 21:57:56.514 UTC [1] LOG C-0x562e437743f0: postgres/postgres@192.168.100.9:51156 login attempt: db=postgres user=postgres tls=no
monitor    | [21:57:56] READ: Total records=984, Latest: ID=1039, Data='Test data #1008'
pgbouncer  | 2025-08-10 21:57:56.515 UTC [1] LOG C-0x562e437743f0: postgres/postgres@192.168.100.9:51156 closing because: client close request (age=0s)
pg2        | 2025-08-10 21:57:56,638 INFO: no action. I am (pg2), the leader with the lock
pgbouncer  | 2025-08-10 21:57:57.517 UTC [1] LOG C-0x562e437743f0: postgres/postgres@192.168.100.9:51164 login attempt: db=postgres user=postgres tls=no
pg2        | 2025-08-10 21:57:57.518 UTC [265] ERROR:  cannot execute INSERT in a read-only transaction
pg2        | 2025-08-10 21:57:57.518 UTC [265] STATEMENT:  INSERT INTO test_data (data, node_name) VALUES ('Test data #77', 'postgres-cluster') RETURNING id
monitor    | [21:57:57] WRITE ERROR: cannot execute INSERT in a read-only transaction
monitor    | ...
pgbouncer  | 2025-08-10 21:57:57.518 UTC [1] LOG C-0x562e437743f0: postgres/postgres@192.168.100.9:51164 closing because: client close request (age=0s)
pgbouncer  | 2025-08-10 21:57:57.518 UTC [1] LOG C-0x562e437743f0: postgres/postgres@192.168.100.9:51174 login attempt: db=postgres user=postgres tls=no
monitor    | [21:57:57] READ: Total records=984, Latest: ID=1039, Data='Test data #1008'
pgbouncer  | 2025-08-10 21:57:57.519 UTC [1] LOG C-0x562e437743f0: postgres/postgres@192.168.100.9:51174 closing because: client close request (age=0s)
pgbouncer  | 2025-08-10 21:57:58.520 UTC [1] LOG C-0x562e437743f0: postgres/postgres@192.168.100.9:51182 login attempt: db=postgres user=postgres tls=no
pg2        | 2025-08-10 21:57:58.521 UTC [265] ERROR:  cannot execute INSERT in a read-only transaction
pg2        | 2025-08-10 21:57:58.521 UTC [265] STATEMENT:  INSERT INTO test_data (data, node_name) VALUES ('Test data #77', 'postgres-cluster') RETURNING id
monitor    | [21:57:58] WRITE ERROR: cannot execute INSERT in a read-only transaction
monitor    | ...
pgbouncer  | 2025-08-10 21:57:58.522 UTC [1] LOG C-0x562e437743f0: postgres/postgres@192.168.100.9:51182 closing because: client close request (age=0s)
pgbouncer  | 2025-08-10 21:57:58.522 UTC [1] LOG C-0x562e437743f0: postgres/postgres@192.168.100.9:51196 login attempt: db=postgres user=postgres tls=no
monitor    | [21:57:58] READ: Total records=984, Latest: ID=1039, Data='Test data #1008'
pgbouncer  | 2025-08-10 21:57:58.524 UTC [1] LOG C-0x562e437743f0: postgres/postgres@192.168.100.9:51196 closing because: client close request (age=0s)
pg2        | 2025-08-10 21:57:58.721 UTC [252] FATAL:  could not connect to the primary server: could not translate host name "pg1" to address: Name or service not known
pg2        | 2025-08-10 21:57:58.721 UTC [33] LOG:  redo done at 0/4015E88 system usage: CPU: user: 0.00 s, system: 0.00 s, elapsed: 280.38 s
pg2        | 2025-08-10 21:57:58.721 UTC [33] LOG:  last completed transaction was at log time 2025-08-10 21:57:23.196882+00
pg2        | 2025-08-10 21:57:58.763 UTC [33] LOG:  selected new timeline ID: 3
pg2        | 2025-08-10 21:57:58.817 UTC [33] LOG:  archive recovery complete
pg2        | 2025-08-10 21:57:58.828 UTC [31] LOG:  checkpoint starting: force
pg2        | 2025-08-10 21:57:58.833 UTC [29] LOG:  database system is ready to accept connections
pgbouncer  | 2025-08-10 21:57:59.526 UTC [1] LOG C-0x562e437743f0: postgres/postgres@192.168.100.9:51206 login attempt: db=postgres user=postgres tls=no
monitor    | [21:57:59] WRITE: ID=232, Data='Test data #77'
pgbouncer  | 2025-08-10 21:57:59.534 UTC [1] LOG C-0x562e437743f0: postgres/postgres@192.168.100.9:51206 closing because: client close request (age=0s)
pgbouncer  | 2025-08-10 21:57:59.534 UTC [1] LOG C-0x562e437743f0: postgres/postgres@192.168.100.9:51222 login attempt: db=postgres user=postgres tls=no
monitor    | [21:57:59] READ: Total records=985, Latest: ID=1039, Data='Test data #1008'
pgbouncer  | 2025-08-10 21:57:59.536 UTC [1] LOG C-0x562e437743f0: postgres/postgres@192.168.100.9:51222 closing because: client close request (age=0s)
monitor    | [21:57:59] Connection restored after 5 failures
pg2        | 2025-08-10 21:57:59,594 INFO: Lock owner: pg2; I am pg2
pg2        | 2025-08-10 21:57:59,689 INFO: Reaped pid=272, exit status=0
pg2        | 2025-08-10 21:57:59.718 UTC [31] LOG:  checkpoint complete: wrote 20 buffers (0.1%); 0 WAL file(s) added, 0 removed, 0 recycled; write=0.847 s, sync=0.019 s, total=0.891 s; sync files=14, longest=0.005 s, average=0.002 s; distance=87 kB, estimate=87 kB; lsn=0/4019140, redo lsn=0/4015EE0
pg2        | 2025-08-10 21:57:59.718 UTC [31] LOG:  checkpoint starting: immediate force wait
pg2        | 2025-08-10 21:57:59.752 UTC [31] LOG:  checkpoint complete: wrote 4 buffers (0.0%); 0 WAL file(s) added, 0 removed, 0 recycled; write=0.009 s, sync=0.007 s, total=0.035 s; sync files=4, longest=0.004 s, average=0.002 s; distance=12 kB, estimate=80 kB; lsn=0/40191F0, redo lsn=0/40191B8
pg2        | 2025-08-10 21:57:59,788 INFO: no action. I am (pg2), the leader with the lock
pg2        | 2025-08-10 21:57:59,936 INFO: no action. I am (pg2), the leader with the lock
pgbouncer  | 2025-08-10 21:58:00.538 UTC [1] LOG C-0x562e437743f0: postgres/postgres@192.168.100.9:51226 login attempt: db=postgres user=postgres tls=no
monitor    | [21:58:00] WRITE: ID=233, Data='Test data #78'
pgbouncer  | 2025-08-10 21:58:00.545 UTC [1] LOG C-0x562e437743f0: postgres/postgres@192.168.100.9:51226 closing because: client close request (age=0s)
pgbouncer  | 2025-08-10 21:58:00.546 UTC [1] LOG C-0x562e437743f0: postgres/postgres@192.168.100.9:51240 login attempt: db=postgres user=postgres tls=no
monitor    | [21:58:00] READ: Total records=986, Latest: ID=1039, Data='Test data #1008'
pgbouncer  | 2025-08-10 21:58:00.547 UTC [1] LOG C-0x562e437743f0: postgres/postgres@192.168.100.9:51240 closing because: client close request (age=0s)
pgbouncer  | 2025-08-10 21:58:01.548 UTC [1] LOG C-0x562e437743f0: postgres/postgres@192.168.100.9:51160 login attempt: db=postgres user=postgres tls=no
monitor    | [21:58:01] WRITE: ID=234, Data='Test data #79'
```

Here's what happens:
- The failure occurs at 21:57:23, when pg1 is stopped
- pg2 is promoted to primary at 21:57:43
- haproxy detects the change at 21:57:47 and starts routing traffic to pg2
- pg2 becomes operational as the new primary at 21:57:59

At this point, pg2 is the new primary:

```bash
$ docker exec pg2 patronictl -c /etc/patroni.yml list
+ Cluster: postgres-cluster (7537073505429905430) --+
| Member | Host | Role   | State   | TL | Lag in MB |
+--------+------+--------+---------+----+-----------+
| pg2    | pg2  | Leader | running |  3 |           |
+--------+------+--------+---------+----+-----------+
```

Now let's start pg1 again:

```bash
docker-compose up pg1 -d
```

Checking the status again, I discover a failure:

```bash
$ docker exec pg2 patronictl -c /etc/patroni.yml list
+ Cluster: postgres-cluster (7537073505429905430) --------+
| Member | Host | Role    | State        | TL | Lag in MB |
+--------+------+---------+--------------+----+-----------+
| pg1    | pg1  | Replica | start failed |    |   unknown |
| pg2    | pg2  | Leader  | running      |  3 |           |
+--------+------+---------+--------------+----+-----------+
```

According to the logs, pg1 is out of sync:

```bash
Error: WAL location 0/4000000 belongs to timeline 2, but previous recovered WAL file came from timeline 3
```

To reinitialize pg1 and bring it back into the cluster, run:

```bash
docker exec pg2 patronictl -c /etc/patroni.yml reinit postgres-cluster pg1 --force
```

Now everything is back to normal:

```bash
$ docker exec pg2 patronictl -c /etc/patroni.yml list
+ Cluster: postgres-cluster (7537073505429905430) -----+
| Member | Host | Role    | State     | TL | Lag in MB |
+--------+------+---------+-----------+----+-----------+
| pg1    | pg1  | Replica | streaming |  3 |         0 |
| pg2    | pg2  | Leader  | running   |  3 |           |
+--------+------+---------+-----------+----+-----------+
```

This failover is completely transparent to the application; Issues like the temporary read-only state of pg2 during the failover should be handled by the application logic.