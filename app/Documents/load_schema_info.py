from settings.setting import *
from langchain.schema import Document
import pandas as pd

def get_tables_description_purpose():
    file = pd.read_excel(EXCEL_FILE_PATH, sheet_name="Table Schema & Description")
    file.columns = file.iloc[2]
    file.drop(index=[0, 1, 2], inplace=True)
    file.columns = ["Empty", "Table_Name", "Purpose", "Description"]
    file.drop(columns=['Empty'], inplace=True)
    file.reset_index(drop=True, inplace=True)
    print(file)
    return file

## DoseSync
# file = pd.read_excel(EXCEL_FILE_PATH, sheet_name="Sheet2")
# file.columns = ["Empty", "Table_Name", "Purpose", "Description"]
# file.drop(columns=['Empty'], inplace=True)
# file.drop(index=[0], inplace=True)
# file.reset_index(drop=True, inplace=True)
# print(file)
# return file

def get_schema_dictionary():
    try:
        database_schema_info = []
        file = get_tables_description_purpose()

        for table_name, schema in SCHEMA_DICT.items():
            table_schema_info = {}
            try:
                index_list = file[file['Table_Name'] == table_name].index
                index = index_list[0]
                print(f"Index is: {index}\n")
                table_schema_info['Table_name'] = table_name
                table_schema_info['schema'] = f'{table_name}\n{schema}'
                table_schema_info['Purpose'] = file['Purpose'][index]
                table_schema_info['Description'] = file['Description'][index]
                table_schema_info['Content'] = f"Table_Name:- {table_name}\nPurpose:- {file['Purpose'][index]}\nDescription:- {file['Description'][index]}\nSchema:- {schema}"

                print(f"\n Schema: {schema}\n")
                print("==================================================================")

                database_schema_info.append(table_schema_info)

            except IndexError as e:
                print("Without index")
                table_schema_info['Table_name'] = table_name
                table_schema_info['schema'] = schema
                table_schema_info['Purpose'] = " "
                table_schema_info['Description'] = " "
                table_schema_info['Content'] = f'Table_Name:- {table_name}\nSchema:- {schema}'

                print(f"\n Schema when IndexError: {schema}\n")
                print("==================================================================")

                database_schema_info.append(table_schema_info)

        return database_schema_info

    except Exception as e:
        print(f"Exception has been occurred during get the schema of the tables: {e}")
        raise Exception("Exception has been occurred during get the schema of the tables")

def get_schema_documents():
    documents = []
    file = get_tables_description_purpose()

    for table_name, schema in SCHEMA_DICT.items():
        try:
            index_list = file[file['Table_Name'] == table_name].index
            index = index_list[0]
            purpose = file['Purpose'][index]
            description = file['Description'][index]
            content = f'Table_Name:- {table_name}\nPurpose:- {purpose}\nDescription:- {description}\nSchema:- {schema}'

            documents.append(Document(page_content=content, metadata={'source': table_name}))

        except IndexError as e:
            documents.append(Document(page_content=f'Table_Name:- {table_name}\nSchema:- {schema}', metadata={'source': table_name}))
        
    return documents

def get_api_dictionary():
    file = pd.read_excel(EXCEL_FILE_PATH, sheet_name="CRM API Description")

    ## Drop the first row from the file
    # file.drop(index=0, inplace=True)

    ## Reset the index
    file.reset_index(drop=True, inplace=True)

    apis = []

    for i in range(0, len(file)):
        api_name = file['API Name'][i]
        endpoint = file['Endpoint'][i]
        description = file['Description'][i]
        required_fields = file['Required fields'][i]

        page_content = f"{api_name}\n{endpoint}\n{description}\n{required_fields}"

        api = {'Name': api_name, 'Endpoint': endpoint, 'Description': description, 'Required fields': required_fields, "Page_content": page_content}

        apis.append(api)

    return apis

def get_api_documents():
    file = pd.read_excel(EXCEL_FILE_PATH, sheet_name="CRM API Description")

    ## Drop the first row from the file
    file.drop(index=0, inplace=True)

    ## Reset the index
    file.reset_index(drop=True, inplace=True)

    apis = []

    for i in range(0, len(file)):
        api_name = file['API Name'][i]
        endpoint = file['Endpoint'][i]
        description = file['Description'][i]
        required_fields = file['Required fields'][i]

        page_content = f"{api_name}\n{endpoint}\n{description}\n{required_fields}"

        apis.append(Document(page_content=page_content, metadata= {'Name': api_name, 'Endpoint': endpoint, 'Description': description,'Required fields': required_fields}))

    return apis

def get_faqs_dictionary():

    file = get_tables_description_purpose()

    # faqs_list_dictionary = [{"user_query": "How many packs have been affected due to the batch change of the batch id 1.", "sql_query": "SELECT COUNT(*) FROM batch_change_tracker WHERE batch_id_id=1", "table_name": ['batch_change_tracker'], "content": []},
    #                         {"user_query": "Give me the patient name of the pack_id 449047", "sql_query": "SELECT first_name, last_name FROM patient_master WHERE id IN (SELECT patient_id_id FROM patient_rx WHERE id IN (SELECT patient_rx_id_id FROM pack_rx_link WHERE pack_id_id=449047))", "table_name": ["patient_master", "patient_rx", "pack_rx_link"], "content": []},
    #                         {"user_query": "Give me list of drug names inside the pack id 449047", "sql_query": "SELECT drug_name FROM drug_master WHERE id IN (SELECT original_drug_id_id FROM pack_rx_link WHERE pack_id_id=449047", "table_name": ['drug_master', 'pack_rx_link'], "content": []},
    #                         {"user_query": "Give me drug names of the according to the slots of the pack id 449047", "sql_query": "SELECT drug_master.drug_name, slot_details.slot_id_id FROM drug_master WHERE id IN (SELECT drug_id_id FROM slot_details WHERE pack_rx_id_id IN (SELECT id FROM pack_rx_link WHERE pack_id_id=449047", "table_name": ["drug_master", "slot_details", "pack_rx_link"], "content": []},
    #                         {"user_query": "give me the drug names of the canister id 8448", "sql_query": "SELECT drug_name FROM drug_master WHERE id IN (SELECT drug_id_id FROM canister_tracker WHERE canister_id_id=8448", "table_name": ["canister_tracker", "drug_master"], "content": []}]
    faqs_list_dictionary = []
    for d in faqs_list_dictionary:
        for key, value in d.items():
            if key == 'table_name':
                table_contents = []
                for table_name in value:
                    try:
                        index_list = file[file['Table_Name'] == table_name].index
                        index = index_list[0]
                        purpose = file['Purpose'][index]
                        description = file['Description'][index]
                        content = f'Table_Name:- {table_name}\nPurpose:- {purpose}\nDescription:- {description}\nSchema:- {SCHEMA_DICT[table_name]}'
                        table_contents.append(content)

                    except IndexError as e:
                        content = f'Table_Name:- {table_name}\nSchema:- {SCHEMA_DICT[table_name]}'
                        table_contents.append(content)

                d['content'] = table_contents

    return faqs_list_dictionary

def get_faqs_documents():
    faqs_info = get_faqs_dictionary()

    faqs_documents = []

    for faqs in faqs_info:
        faqs_user_query = faqs['user_query']
        faqs_sql_query = faqs['sql_query']
        faqs_table = faqs['table_name']
        table_info = faqs['content']
        faqs_content = f"{faqs_user_query}"
        faqs_documents.append(Document(page_content=faqs_content, metadata = {'table_info': f'{table_info}', 'table_name': faqs_table, 'sql_query': faqs_sql_query}))

    return faqs_documents
