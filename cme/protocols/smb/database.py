#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import logging
from sqlalchemy import func, text


class database:
    def __init__(self, conn, metadata=None):
        # this is still named "conn" when it is the Session object, TODO: rename
        self.conn = conn
        self.metadata = metadata
        self.computers_table = metadata.tables["computers"]
        self.users_table = metadata.tables["users"]
        self.groups_table = metadata.tables["groups"]
        self.shares_table = metadata.tables["shares"]
        self.admin_relations_table = metadata.tables["admin_relations"]
        self.group_relations_table = metadata.tables["group_relations"]
        self.loggedin_relations = metadata.tables["loggedin_relations"]

    @staticmethod
    def db_schema(db_conn):
        db_conn.execute('''CREATE TABLE "computers" (
            "id" integer PRIMARY KEY,
            "ip" text,
            "hostname" text,
            "domain" text,
            "os" text,
            "dc" boolean,
            "smbv1" boolean,
            "signing" boolean,
            "spooler" boolean,
            "zerologon" boolean,
            "petitpotam" boolean
            )''')

        # type = hash, plaintext
        db_conn.execute('''CREATE TABLE "users" (
            "id" integer PRIMARY KEY,
            "domain" text,
            "username" text,
            "password" text,
            "credtype" text,
            "pillaged_from_computerid" integer,
            FOREIGN KEY(pillaged_from_computerid) REFERENCES computers(id)
            )''')

        db_conn.execute('''CREATE TABLE "groups" (
            "id" integer PRIMARY KEY,
            "domain" text,
            "name" text
            )''')

        # This table keeps track of which credential has admin access over which machine and vice-versa
        db_conn.execute('''CREATE TABLE "admin_relations" (
            "id" integer PRIMARY KEY,
            "userid" integer,
            "computerid" integer,
            FOREIGN KEY(userid) REFERENCES users(id),
            FOREIGN KEY(computerid) REFERENCES computers(id)
            )''')

        db_conn.execute('''CREATE TABLE "loggedin_relations" (
            "id" integer PRIMARY KEY,
            "userid" integer,
            "computerid" integer,
            FOREIGN KEY(userid) REFERENCES users(id),
            FOREIGN KEY(computerid) REFERENCES computers(id)
            )''')

        db_conn.execute('''CREATE TABLE "group_relations" (
            "id" integer PRIMARY KEY,
            "userid" integer,
            "groupid" integer,
            FOREIGN KEY(userid) REFERENCES users(id),
            FOREIGN KEY(groupid) REFERENCES groups(id)
            )''')

        db_conn.execute('''CREATE TABLE "shares" (
            "id" integer PRIMARY KEY,
            "computerid" text,
            "userid" integer,
            "name" text,
            "remark" text,
            "read" boolean,
            "write" boolean,
            FOREIGN KEY(userid) REFERENCES users(id)
            UNIQUE(computerid, userid, name)
        )''')

        #db_conn.execute('''CREATE TABLE "ntds_dumps" (
        #    "id" integer PRIMARY KEY,
        #    "computerid", integer,
        #    "domain" text,
        #    "username" text,
        #    "hash" text,
        #    FOREIGN KEY(computerid) REFERENCES computers(id)
        #    )''')

    def add_share(self, computerid, userid, name, remark, read, write):
        data = {
            "computerid": computerid,
            "userid": userid,
            "name": name,
            "remark": remark,
            "read": read,
            "write": write,
        }
        self.conn.execute(
            self.shares_table.insert(),
            [data]
        )
        self.conn.commit()
        self.conn.close()

    def is_share_valid(self, share_id):
        """
        Check if this share ID is valid.
        """
        results = self.conn.query(self.shares_table).filter(
            self.shares_table.c.id == share_id
        ).all()
        self.conn.commit()
        self.conn.close()

        logging.debug(f"is_share_valid(shareID={share_id}) => {len(results) > 0}")
        return len(results) > 0

    def get_shares(self, filter_term=None):
        if self.is_share_valid(filter_term):
            results = self.conn.query(self.shares_table).filter(
                self.shares_table.c.id == filter_term
            ).all()
        elif filter_term:
            results = self.conn.query(self.shares_table).filter(
                func.lower(self.shares_table.c.name).like(func.lower(f"%{filter_term}%"))
            ).all()
        else:
            results = self.conn.query(self.shares_table).all()
        return results

    def get_shares_by_access(self, permissions, share_id=None):
        permissions = permissions.lower()

        if share_id:
            if permissions == "r":
                results = self.conn.query(self.shares_table).filter(
                    self.shares_table.c.id == share_id,
                    self.shares_table.c.read == 1
                ).all()
            elif permissions == "w":
                results = self.conn.query(self.shares_table).filter(
                    self.shares_table.c.id == share_id,
                    self.shares_table.c.write == 1
                ).all()
            elif permissions == "rw":
                results = self.conn.query(self.shares_table).filter(
                    self.shares_table.c.id == share_id,
                    self.shares_table.c.read == 1,
                    self.shares_table.c.write == 1
                ).all()
        else:
            if permissions == "r":
                results = self.conn.query(self.shares_table).filter(
                    self.shares_table.c.read == 1
                ).all()
            elif permissions == "w":
                results = self.conn.query(self.shares_table).filter(
                    self.shares_table.c.write == 1
                ).all()
            elif permissions == "rw":
                results = self.conn.query(self.shares_table).filter(
                    self.shares_table.c.read == 1,
                    self.shares_table.c.write == 1
                ).all()
        return results

    def get_users_with_share_access(self, computer_id, share_name, permissions):
        permissions = permissions.lower()

        if permissions == "r":
            results = self.conn.query(self.shares_table.c.userid).filter(
                self.shares_table.c.computerid == computer_id,
                self.shares_table.c.name == share_name,
                self.shares_table.c.read == 1
            ).all()
        elif permissions == "w":
            results = self.conn.query(self.shares_table.c.userid).filter(
                self.shares_table.c.computerid == computer_id,
                self.shares_table.c.name == share_name,
                self.shares_table.c.write == 1
            ).all()
        elif permissions == "rw":
            results = self.conn.query(self.shares_table.c.userid).filter(
                self.shares_table.c.computerid == computer_id,
                self.shares_table.c.name == share_name,
                self.shares_table.c.read == 1,
                self.shares_table.c.write == 1
            ).all()
        return results

    # pull/545
    def add_computer(self, ip, hostname, domain, os, smbv1, signing=None, spooler=None, zerologon=None, petitpotam=None, dc=None):
        """
        Check if this host has already been added to the database, if not add it in.
        """
        domain = domain.split('.')[0].upper()

        results = self.conn.query(self.computers_table).filter(
            self.computers_table.c.ip == ip
        ).all()
        data = {}
        if ip is not None:
            data["ip"] = ip
        if hostname is not None:
            data["hostname"] = hostname
        if domain is not None:
            data["domain"] = domain
        if os is not None:
            data["os"] = os
        if smbv1 is not None:
            data["smbv1"] = smbv1
        if signing is not None:
            data["signing"] = signing
        if spooler is not None:
            data["spooler"] = spooler
        if zerologon is not None:
            data["zerologon"] = zerologon
        if petitpotam is not None:
            data["petitpotam"] = petitpotam
        if dc is not None:
            data["dc"] = dc
        print(f"DATA: {data}")

        print(f"RESULTS: {results}")

        if not results:
            print(f"IP: {ip}")
            print(f"Hostname: {hostname}")
            print(f"Domain: {domain}")
            print(f"OS: {os}")
            print(f"SMB: {smbv1}")
            print(f"Signing: {signing}")
            print(f"DC: {dc}")

            new_host = {
                "ip": ip,
                "hostname": hostname,
                "domain": domain,
                "os": os,
                "dc": dc,
                "smbv1": smbv1,
                "signing": signing,
                "spooler": spooler,
                "zerologon": zerologon,
                "petitpotam": petitpotam
            }
            try:
                cid = self.conn.execute(
                    self.computers_table.insert(),
                    [new_host]
                )
            except Exception as e:
                print(f"Exception: {e}")
                #self.conn.execute("INSERT INTO computers (ip, hostname, domain, os, dc) VALUES (?,?,?,?,?)", [ip, hostname, domain, os, dc])
        else:
            for host in results:
                print(host.id)
                print(f"Host: {host}")
                print(f"Host Type: {type(host)}")
                try:
                    cid = self.conn.execute(
                        self.computers_table.update().values(
                            data
                        ).where(
                            self.computers_table.c.id == host.id
                        )
                    )
                    self.conn.commit()
                except Exception as e:
                    print(f"Exception: {e}")
                # try:
                #     if (hostname != host[2]) or (domain != host[3]) or (os != host[4]) or (smbv1 != host[6]) or (signing != host[7]):
                #         self.conn.execute("UPDATE computers SET hostname=?, domain=?, os=?, smbv1=?, signing=?, spooler=?, zerologon=?, petitpotam=? WHERE id=?", [hostname, domain, os, smbv1, signing, spooler, zerologon, petitpotam, host[0]])
                # except:
                #     if (hostname != host[2]) or (domain != host[3]) or (os != host[4]):
                #         self.conn.execute("UPDATE computers SET hostname=?, domain=?, os=? WHERE id=?", [hostname, domain, os, host[0]])
                # if dc != None and (dc != host[5]):
                #     self.conn.execute("UPDATE computers SET dc=? WHERE id=?", [dc, host[0]])
        self.conn.commit()
        self.conn.close()

        return cid

    def update_computer(self, host_id, hostname=None, domain=None, os=None, smbv1=None, signing=None, spooler=None, zerologon=None, petitpotam=None, dc=None):
        data = {
            "id": host_id,
            "spooler": spooler
        }
        # Computers.Update(data)
        # self.conn.execute(Computers.Update(data))

    def add_credential(self, credtype, domain, username, password, groupid=None, pillaged_from=None):
        """
        Check if this credential has already been added to the database, if not add it in.
        """
        domain = domain.split('.')[0].upper()
        user_rowid = None

        if groupid and not self.is_group_valid(groupid):
            self.conn.close()
            return

        if pillaged_from and not self.is_computer_valid(pillaged_from):
            self.conn.close()
            return

        results = self.conn.query(self.users_table).filter(
            func.lower(self.users_table.c.domain) == func.lower(domain),
            func.lower(self.users_table.c.username) == func.lower(username),
            func.lower(self.users_table.c.credtype) == func.lower(credtype)
        ).all()
        logging.debug(f"Credential results: {results}")

        if not results:
            data = {
                "domain": domain,
                "username": username,
                "password": password,
                "credtype": credtype,
                "pillaged_from_computerid": pillaged_from,
            }
            #self.conn.execute("INSERT INTO users (domain, username, password, credtype, pillaged_from_computerid) VALUES (?,?,?,?,?)", [domain, username, password, credtype, pillaged_from])
            user_rowid = self.conn.execute(
                self.users_table.insert(),
                [data]
            )
            logging.debug(f"User RowID: {user_rowid}")
            #user_rowid = self.conn.lastrowid
            if groupid:
                gr_data = {
                    "userid": user_rowid,
                    "groupid": groupid,
                }
                #self.conn.execute("INSERT INTO group_relations (userid, groupid) VALUES (?,?)", [user_rowid, groupid])
                self.conn.execute(
                    self.group_relations_table.insert(),
                    [gr_data]
                )
            self.conn.commit()
        else:
            for user in results:
                if not user[3] and not user[4] and not user[5]:
                    self.conn.execute('UPDATE users SET password=?, credtype=?, pillaged_from_computerid=? WHERE id=?', [password, credtype, pillaged_from, user[0]])
                    user_rowid = self.conn.lastrowid
                    if groupid and not len(self.get_group_relations(user_rowid, groupid)):
                        self.conn.execute("INSERT INTO group_relations (userid, groupid) VALUES (?,?)", [user_rowid, groupid])

        self.conn.commit()
        self.conn.close()

        logging.debug('add_credential(credtype={}, domain={}, username={}, password={}, groupid={}, pillaged_from={}) => {}'.format(credtype, domain, username, password, groupid, pillaged_from, user_rowid))

        return user_rowid

    def add_user(self, domain, username, groupid=None):
        if groupid and not self.is_group_valid(groupid):
            return

        domain = domain.split('.')[0].upper()
        user_rowid = None

        self.conn.execute("SELECT * FROM users WHERE LOWER(domain)=LOWER(?) AND LOWER(username)=LOWER(?)", [domain, username])
        results = self.conn.fetchall()

        if not len(results):
            self.conn.execute("INSERT INTO users (domain, username, password, credtype, pillaged_from_computerid) VALUES (?,?,?,?,?)", [domain, username, '', '', ''])
            user_rowid = self.conn.lastrowid
            if groupid:
                self.conn.execute("INSERT INTO group_relations (userid, groupid) VALUES (?,?)", [user_rowid, groupid])
        else:
            for user in results:
                if (domain != user[1]) and (username != user[2]):
                    self.conn.execute("UPDATE users SET domain=?, user=? WHERE id=?", [domain, username, user[0]])
                    user_rowid = self.conn.lastrowid

                if not user_rowid: user_rowid = user[0]
                if groupid and not len(self.get_group_relations(user_rowid, groupid)):
                    self.conn.execute("INSERT INTO group_relations (userid, groupid) VALUES (?,?)", [user_rowid, groupid])

        self.conn.commit()
        self.conn.close()

        logging.debug('add_user(domain={}, username={}, groupid={}) => {}'.format(domain, username, groupid, user_rowid))

        return user_rowid

    def add_group(self, domain, name):
        domain = domain.split('.')[0].upper()

        self.conn.execute("SELECT * FROM groups WHERE LOWER(domain)=LOWER(?) AND LOWER(name)=LOWER(?)", [domain, name])
        results = self.conn.fetchall()

        if not len(results):
            self.conn.execute("INSERT INTO groups (domain, name) VALUES (?,?)", [domain, name])

        self.conn.commit()
        self.conn.close()

        logging.debug('add_group(domain={}, name={}) => {}'.format(domain, name, self.conn.lastrowid))

        return self.conn.lastrowid

    def remove_credentials(self, creds_id):
        """
        Removes a credential ID from the database
        """
        for cred_id in creds_id:
            self.conn.execute("DELETE FROM users WHERE id=?", [cred_id])
            self.conn.commit()
        self.conn.close()

    def add_admin_user(self, credtype, domain, username, password, host, user_id=None):
        domain = domain.split('.')[0].upper()

        if user_id:
            users = self.conn.query(self.users_table).filter(
                self.users_table.c.id == user_id
            ).all()
        else:
            users = self.conn.query(self.users_table).filter(
                self.users_table.c.credtype == credtype,
                func.lower(self.users_table.c.domain) == func.lower(domain),
                func.lower(self.users_table.c.username) == func.lower(username),
                self.users_table.c.password == password
            ).all()
        logging.debug(f"Users: {users}")

        hosts = self.conn.query(self.computers_table).filter(
            self.computers_table.c.ip.like(func.lower(f"%{host}%"))
        )
        logging.debug(f"Hosts: {hosts}")

        if users is not None and hosts is not None:
            for user, host in zip(users, hosts):
                user_id = user[0]
                host_id = host[0]

                # Check to see if we already added this link
                links = self.conn.query(self.admin_relations_table).filter(
                    self.admin_relations_table.c.userid == user_id,
                    self.admin_relations_table.c.computerid == host_id
                ).all()

                if not links:
                    self.conn.execute(
                        self.admin_relations_table.insert(),
                        [{"userid": user_id, "computerid": host_id}]
                    )
                    self.conn.commit()

        self.conn.commit()
        self.conn.close()

    def get_admin_relations(self, user_id=None, host_id=None):
        if user_id:
            results = self.conn.query(self.admin_relations_table).filter(
                self.admin_relations_table.c.userid == user_id
            ).all()
        elif host_id:
            results = self.conn.query(self.admin_relations_table).filter(
                self.admin_relations_table.c.computerid == host_id
            ).all()
        else:
            results = self.conn.query(self.admin_relations_table).all()

        self.conn.commit()
        self.conn.close()
        return results

    def get_group_relations(self, user_id=None, group_id=None):
        if user_id and group_id:
            self.conn.execute("SELECT * FROM group_relations WHERE userid=? and groupid=?", [user_id, group_id])

        elif user_id:
            self.conn.execute("SELECT * FROM group_relations WHERE userid=?", [user_id])

        elif group_id:
            self.conn.execute("SELECT * FROM group_relations WHERE groupid=?", [group_id])

        results = self.conn.fetchall()
        self.conn.commit()
        self.conn.close()

        return results

    def remove_admin_relation(self, userIDs=None, hostIDs=None):
        if userIDs:
            for userID in userIDs:
                self.conn.execute("DELETE FROM admin_relations WHERE userid=?", [userID])

        elif hostIDs:
            for hostID in hostIDs:
                self.conn.execute("DELETE FROM admin_relations WHERE hostid=?", [hostID])

        self.conn.commit()
        self.conn.close()

    def remove_group_relations(self, userID=None, groupID=None):
        if userID:
            self.conn.execute("DELETE FROM group_relations WHERE userid=?", [userID])

        elif groupID:
            self.conn.execute("DELETE FROM group_relations WHERE groupid=?", [groupID])

        results = self.conn.fetchall()
        self.conn.commit()
        self.conn.close()

        return results

    def is_credential_valid(self, credential_id):
        """
        Check if this credential ID is valid.
        """
        results = self.conn.query(self.users_table).filter(
            self.users_table.c.id == credential_id,
            self.users_table.c.password is not None
        ).all()
        self.conn.commit()
        self.conn.close()
        return len(results) > 0

    def is_credential_local(self, credentialID):
        self.conn.execute('SELECT domain FROM users WHERE id=?', [credentialID])
        user_domain = self.conn.fetchall()

        if user_domain:
            self.conn.execute('SELECT * FROM computers WHERE LOWER(hostname)=LOWER(?)', [user_domain])
            results = self.conn.fetchall()
            self.conn.commit()
            self.conn.close()
            return len(results) > 0

    def get_credentials(self, filter_term=None, cred_type=None):
        """
        Return credentials from the database.
        """
        # if we're returning a single credential by ID
        if self.is_credential_valid(filter_term):
            results = self.conn.query(self.users_table).filter(
                self.users_table.c.id == filter_term
            ).all()
        elif cred_type:
            results = self.conn.query(self.users_table).filter(
                self.users_table.c.credtype == cred_type
            ).all()
        # if we're filtering by username
        elif filter_term and filter_term != '':
            results = self.conn.query(self.users_table).filter(
                func.lower(self.users_table.c.username).like(func.lower(f"%{filter_term}%"))
            ).all()
        # otherwise return all credentials
        else:
            results = self.conn.query(self.users_table).all()

        self.conn.commit()
        self.conn.close()
        return results

    def is_user_valid(self, userID):
        """
        Check if this User ID is valid.
        """
        self.conn.execute('SELECT * FROM users WHERE id=? LIMIT 1', [userID])
        results = self.conn.fetchall()
        self.conn.commit()
        self.conn.close()
        return len(results) > 0

    def get_users(self, filterTerm=None):
        if self.is_user_valid(filterTerm):
            self.conn.execute("SELECT * FROM users WHERE id=? LIMIT 1", [filterTerm])

        # if we're filtering by username
        elif filterTerm and filterTerm != '':
            self.conn.execute("SELECT * FROM users WHERE LOWER(username) LIKE LOWER(?)", ['%{}%'.format(filterTerm)])

        else:
            self.conn.execute("SELECT * FROM users")

        results = self.conn.fetchall()
        self.conn.commit()
        self.conn.close()
        return results

    def get_user(self, domain, username):
        results = self.conn.query(self.users_table).filter(
            func.lower(self.users_table.c.domain) == func.lower(domain),
            func.lower(self.users_table.c.username) == func.lower(username)
        ).all()
        self.conn.commit()
        self.conn.close()
        return results

    def is_computer_valid(self, hostID):
        """
        Check if this host ID is valid.
        """
        results = self.conn.query(self.computers_table).filter(
            self.computers_table.c.id == hostID
        ).all()
        self.conn.commit()
        self.conn.close()
        return len(results) > 0

    def get_computers(self, filterTerm=None, domain=None):
        """
        Return hosts from the database.
        """
        # if we're returning a single host by ID
        if self.is_computer_valid(filterTerm):
            self.conn.execute("SELECT * FROM computers WHERE id=? LIMIT 1", [filterTerm])
        # if we're filtering by domain controllers
        elif filterTerm == 'dc':
            if domain:
                self.conn.execute("SELECT * FROM computers WHERE dc=1 AND LOWER(domain)=LOWER(?)", [domain])
            else:
                self.conn.execute("SELECT * FROM computers WHERE dc=1")
        # if we're filtering by ip/hostname
        elif filterTerm and filterTerm != "":
            self.conn.execute("SELECT * FROM computers WHERE ip LIKE ? OR LOWER(hostname) LIKE LOWER(?)", ['%{}%'.format(filterTerm), '%{}%'.format(filterTerm)])
        # otherwise return all computers
        else:
            results = self.conn.query(self.computers_table).all()

        self.conn.commit()
        self.conn.close()
        return results

    def get_domain_controllers(self, domain=None):
        return self.get_computers(filterTerm='dc', domain=domain)

    def is_group_valid(self, group_id):
        """
        Check if this group ID is valid.
        """
        results = self.conn.query(self.groups_table).filter(
            self.groups_table.c.id == group_id
        ).first()
        self.conn.commit()
        self.conn.close()

        valid = True if results else False
        logging.debug(f"is_group_valid(groupID={group_id}) => {valid}")

        return valid

    def get_groups(self, filter_term=None, group_name=None, group_domain=None):
        """
        Return groups from the database
        """
        if group_domain:
            group_domain = group_domain.split('.')[0].upper()

        if self.is_group_valid(filter_term):
            results = self.conn.query(self.groups_table).filter(
                self.groups_table.c.id == filter_term
            ).first()
        elif group_name and group_domain:
            results = self.conn.query(self.groups_table).filter(
                func.lower(self.groups_table.c.username) == func.lower(group_name),
                func.lower(self.groups_table.c.domain) == func.lower(group_domain)
            ).all()
        elif filter_term and filter_term != "":
            results = self.conn.query(self.groups_table).filter(
                func.lower(self.groups_table.c.name).like(func.lower(f"%{filter_term}%"))
            ).all()
        else:
            results = self.conn.query(self.groups_table).all()

        self.conn.commit()
        self.conn.close()
        logging.debug(f"get_groups(filterTerm={filter_term}, groupName={group_name}, groupDomain={group_domain}) => {results}")
        return results

    def clear_database(self):
        for table in self.metadata.tables:
            self.conn.query(self.metadata.tables[table]).delete()
        self.conn.commit()
