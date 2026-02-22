import os
import sys
import logging
import pymysql
import json
import boto3
import botocore

logger = logging.getLogger()
logger.setLevel(logging.INFO)


def get_db_credentials():
    secret_id = os.environ["DB_CREDENTIALS_SECRET_ID"]
    sm_client = boto3.client('secretsmanager')
    secret = json.loads(sm_client.get_secret_value(SecretId=secret_id)['SecretString'])
    return secret['username'], secret['password']


def lambda_handler(event, context):

    client = boto3.client('rds')

    source_db_endpoint = event.get("source_db_endpoint")
    target_db_endpoint = event.get("target_db_endpoint")
    user_name, password = get_db_credentials()
    db_name = event.get("db_name")

    src_results = []
    target_results = []
    try:

        print("source db endpoint: " + str(source_db_endpoint))
        print("target db endpoint:" + str(target_db_endpoint))
        print("user:" + str(user_name))
        print("database:" + db_name)

        try:
            src_conn = pymysql.connect(host=source_db_endpoint, user=user_name, passwd=password, db=db_name, connect_timeout=5)

        except pymysql.MySQLError as e:
            logger.error("ERROR: Unexpected error: Could not connect to MySQL instance.")
            logger.error(e)
            sys.exit(1)

        logger.info("SUCCESS: Connection to Source RDS for MySQL instance succeeded")

        try:
            target_conn = pymysql.connect(host= target_db_endpoint, user=user_name, passwd=password, db=db_name, connect_timeout=5)

        except pymysql.MySQLError as e:
            logger.error("ERROR: Unexpected error: Could not connect to MySQL instance.")
            logger.error(e)
            sys.exit(1)

        logger.info("SUCCESS: Connection to Target RDS for MySQL instance succeeded")

        #get product ids from the fail-over DB in the DR region
        src_rows= read_from_db(src_conn)
        if len(src_rows) > 0:
            for (id) in src_rows:
                print("Source product id:" + str(id))
                src_results.append(id)

        print("Total no of products in restored snapshot :" + str(len(src_results)))

        #get product ids from the restored snapshot in the DR region
        target_rows= read_from_db(target_conn)
        if len(target_rows) > 0:
            for (id) in target_rows:
                print("Target product id:" + str(id))
                target_results.append(id)
        print("Total no of products in the fail-over DB in us-west-2:" + str(len(target_results)))


        final_results = []

        # find the diff of products in the fail-over DB and the restored snapshot in the DR region
        diff = find_diff(src_results, target_results)

        cs_diff= ','.join([str(*i) for i in diff])

        if len(diff) > 0:
            for (id) in diff:
                final_results.append(read_all_from_db(target_conn,id))

        print("Total no of products that are not in the fail-over DB in us-west-2:" + str(len(final_results)))
        target_conn.close()
        src_conn.close()

        return final_results

    except botocore.exceptions.ClientError as e:
        logger.error(e)
        raise

    return("reconcliation report generated!!!")

def read_all_from_db(conn, id):
    try:
        id_val= str(*id)
        new_cursor = conn.cursor()

        stmt = "SELECT * FROM product WHERE product_id = %s"
        print("Printing query:" + stmt)
        new_cursor.execute(stmt, (id_val,))
        rows = new_cursor.fetchall()
        return rows

    except Exception as e:
        print(e)
        return None
    finally:
        new_cursor.close()



def read_from_db(conn):
    try:

        cursor = conn.cursor()
        stmt = "SELECT product_id FROM product"
        cursor.execute(stmt)
        rows = cursor.fetchall()
        return rows
    except Exception as e:
        print(e)
        return None
    finally:
        cursor.close()


def find_diff(list1: [], list2: []) -> []:
    return list(set(list1).difference(list2))
