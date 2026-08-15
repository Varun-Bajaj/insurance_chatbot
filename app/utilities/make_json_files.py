import os.path
from settings.setting import *
import json

class BuildJson:
    def __init__(self):
        self.tables = self.get_tables_list()

    def get_tables_list(self):
        tables = []
        DB.execute("SHOW TABLES")

        for table in DB:
            key = list(table.keys())
            tables.append(table[key[0]])

        print(f"No. of tables in the database: {len(tables)}\n")

        return tables

    def make_json_of_fetch_columns_table_wise(self):
        entities = []

        for table in self.tables:
            di = {}
            di["Table_Name"] = table
            cols = []
            DB.execute(f"SHOW COLUMNS FROM `{table}`;")
            columns = DB.fetchall()
            for col in columns:
                cols.append(col['Field'])

            di['field'] = cols

            entities.append(di)

        table_column_details_json_path = os.path.join(os.getcwd(), "data/careloop_table_column_details.json")
        with open(table_column_details_json_path, 'w') as file:
            json.dump(entities, file, indent=4)

    def get_fk_tables(self, table):
        DB.execute("""
            SELECT DISTINCT REFERENCED_TABLE_NAME
            FROM information_schema.KEY_COLUMN_USAGE
            WHERE TABLE_SCHEMA = %s
            AND TABLE_NAME = %s
            AND REFERENCED_TABLE_NAME IS NOT NULL;
        """, ('careloop', table))

        fk_tables = [row['REFERENCED_TABLE_NAME'] for row in DB.fetchall()]

        return fk_tables

    def make_json_of_relationship_between_two_tables(self):
        graph = {}

        for key in self.tables:
            fk_tables = self.get_fk_tables(key)

            for fk_table in fk_tables:
                if key not in graph.keys():
                    graph[key] = [fk_table]

                else:
                    graph[key].append(fk_table)

        graph_info_json_path = os.path.join(os.getcwd(), "data/careloop_graph_info.json")
        with open(graph_info_json_path, 'w') as file:
            json.dump([graph], file, indent=4)

    def make_json_of_database_schema_info(self):
        database_schema_info = []
        table_schema_info = {}

        for table in self.tables:
            print(f"\n{table}\n")
            DB.execute(f"SHOW CREATE TABLE `{table}`;")
            table_schema_dict = DB.fetchone()
            schema = table_schema_dict['Create Table']
            print(f"\n{schema}\n")
            # clean_schema = self.extract_create_table(schema)
            # print(f"\n{clean_schema[0]}\n")
            print("==============================================================")
            table_schema_info[table] = f'{schema}'

        database_schema_info.append(table_schema_info)

        database_schema_info_json_path = os.path.join(os.getcwd(), "data/careloop_database_schema_info.json")
        with open(database_schema_info_json_path, "w") as file:
            json.dump(database_schema_info, file, indent=4)
