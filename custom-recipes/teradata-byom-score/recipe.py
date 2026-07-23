import dataiku
# Import the helpers for custom recipes
from dataiku.customrecipe import *
import pandas as pd
import logging
from verifyTableColumns import *
from querybuilderfacade import *
from inputtableinfo import *
from outputtableinfo import *
from vantage_schema import set_schema_from_vantage
import auth

# Inputs and outputs are defined by roles. In the recipe's I/O tab, the user can associate one
# or more dataset to each input and output role.
# Roles need to be defined in recipe.json, in the inputRoles and outputRoles fields.

    
def verifyOverwriteCache(overwrite_cache, model_name):
    result = ""
    # verify by checking model name
    if bool(overwrite_cache):
        result = f"OverwriteCachedModel({verifyModelName(model_name)})"
    return result

def verifyModelOutputValues(modeloutputfields_values):
    modeloutputfield_list = modeloutputfields_values.split(',')
    stripped_list = []
    for i in range(len(modeloutputfield_list)):
        # value names should not have quotes in them
        value = modeloutputfield_list[i].strip()
        if ('"' in value) or ("'" in value):
            raise Exception('Illegal Value Name', value)
        stripped_list.append(value)
    def listToString(s): 
        str1 =""
        for ele in range(len(s)):  
            str1 += s[ele] + " "
        return str1 
    modeloutputfields_values = listToString(stripped_list).strip().replace(" ","\',\'")
    return f"ModelOutputFields('{modeloutputfields_values}')"


def verifyAccumulate(columnNames):
    # Handle special case
    if columnNames == "*":
        return "Accumulate('*')"
    # column names must be not empty
    if not columnNames:
        raise Exception('Illegal Accumulate Columns', columnNames)
    lst = columnNames.split(',')
    quoted_list = []
    # check all columns are valid
    for columnName in lst:
        # verify and quote column name
        columnName = verifyColumnName(columnName, single_quotes=True)
        quoted_list.append(columnName)
    # return the quoted columns
    accumulate = ",".join(quoted_list)
    return f"Accumulate({accumulate})"



# To  retrieve the datasets of an input role named 'input_A' as an array of dataset names:
input_dataset_name = get_input_names_for_role('input_dataset')[0]
input_dataset = dataiku.Dataset(input_dataset_name)
testing_dataset = input_dataset.get_location_info()['info']['table']
output_dataset_name = get_output_names_for_role('output_dataset')[0]
output_dataset = dataiku.Dataset(output_dataset_name) 

from dataiku.core.sql import SQLExecutor2

scoring_type = str(get_recipe_config()["scoring_type"])
userDBInputChoice = str(get_recipe_config()["user_DBInput_Choice"])

if userDBInputChoice == 'db_drop_down':
    database_name = str(get_recipe_config()["model_database_name"])
elif userDBInputChoice == 'user_db_choice':
    database_name = str(get_recipe_config()["user_Typed_DBName"])


userTBLInputChoice = str(get_recipe_config()["user_TBLInput_Choice"])
if userTBLInputChoice == 'tbl_drop_down':
    table_name = str(get_recipe_config()["table_name"])
elif userTBLInputChoice == 'user_tbl_choice':
    table_name = str(get_recipe_config()["user_Typed_TBLName"])

  
model_name = str(get_recipe_config()["model_name"])

accumulate_all = bool(get_recipe_config()["accumulate_all"])
modeloutputfields_user = bool(get_recipe_config()["modeloutputfields_user"])
predict_func_dbname = str(get_recipe_config()["PMMLPredict_database_name"])
overwrite_cache = get_recipe_config()["overwrite_cache"]
modeloutputfields_values = str(get_recipe_config().get("modeloutputfields_values", ""))
    
if predict_func_dbname == 'user_choice':
    PMMLPredict_db = str(get_recipe_config()["BYOM_Predict_User_DB"])
else:
    PMMLPredict_db = "mldb"
 


if accumulate_all == True:
    accumulate = '*'
if accumulate_all == False:
    accumulate_column_names = get_recipe_config().get("accumulate_column_names", [])
    # convert list to a comma seperated string
    accumulate = ",".join(accumulate_column_names)


conn =  SQLExecutor2(dataset = input_dataset)


# Get the output database and table name
SEP_LENGTH = 80
SEP = "=" * SEP_LENGTH
client = dataiku.api_client()
main_input_name = get_input_names_for_role('input_dataset')[0]
projectkey = main_input_name.split('.')[0]
project = client.get_project(projectkey)

connectionInfo = output_dataset.get_location_info()['info']
outputConnectionName = connectionInfo['connectionName']
connections = {}
connections = auth.addConnection(connections, outputConnectionName)


outputDatabase = output_dataset.get_config()['params'].get('schema', '')
if not outputDatabase:
    outputDatabase = connections[outputConnectionName]['params']['defaultDatabase']
outputTable = connectionInfo['table']

# Setup - pre/post query
try:
    properties = input_dataset.get_location_info(sensitive_info=True)['info'].get('connectionParams').get('properties')
    autocommit = input_dataset.get_location_info(sensitive_info=True)['info'].get('connectionParams').get('autocommitMode')
except:
    inputConnectionName = input_dataset.get_location_info()['info']['connectionName']
    properties = connections[inputConnectionName]['params']['properties']
    autocommit = connections[inputConnectionName]['params']['autocommitMode']

logging.info(SEP)
pre_query = None
post_query = None
if not autocommit:
    logging.info("Assuming TERA mode.")
    pre_query = ["BEGIN TRANSACTION;"]
    post_query = ["END TRANSACTION;"]
    for prop in properties:
        if prop['name'] == 'TMODE':
            if prop['value'] == 'ANSI':
                logging.info("ANSI mode.")
                pre_query = [";"]
                post_query = ["COMMIT WORK;"]

logging.info(SEP)

# Delete old table
executor =  SQLExecutor2(dataset = output_dataset)
try:
    drop_query = f"DROP TABLE {verifyQualifiedTableName(outputDatabase, outputTable)};"
    logging.info(SEP)
    logging.info("DROP query:")
    
    if not autocommit:
        executor.query_to_df(pre_query)
    executor.query_to_df(drop_query, post_queries=post_query)

    logging.info(SEP)
except Exception as e:
    logging.info(e)


#PMML scoring segment. 
if scoring_type == 'pmml':
    if modeloutputfields_user == False:
        query = f"CREATE TABLE {verifyQualifiedTableName(outputDatabase, outputTable)} AS (SELECT * FROM {verifyDatabaseName(PMMLPredict_db)}.PMMLPredict ( ON (select * from {verifyDatabaseName(database_name)}.{verifyDatabaseName(testing_dataset)}) AS InputTable ON (SELECT * FROM {verifyDatabaseName(database_name)}.{verifyTableName(table_name)} WHERE model_id = {verifyModelName(model_name)}) AS ModelTable DIMENSION USING {verifyAccumulate(accumulate)} {verifyOverwriteCache(overwrite_cache, model_name)})AS td) WITH DATA;"
    else:
        query = f"CREATE TABLE {verifyQualifiedTableName(outputDatabase, outputTable)} AS (SELECT * FROM {verifyDatabaseName(PMMLPredict_db)}.PMMLPredict ( ON (select * from {verifyDatabaseName(database_name)}.{verifyDatabaseName(testing_dataset)}) AS InputTable ON (SELECT * FROM {verifyDatabaseName(database_name)}.{verifyTableName(table_name)} WHERE model_id = {verifyModelName(model_name)}) AS ModelTable DIMENSION USING {verifyAccumulate(accumulate)} {verifyModelOutputValues(modeloutputfields_values)} {verifyOverwriteCache(overwrite_cache, model_name)})AS td) WITH DATA;"

#H2O scoring segment
if scoring_type == 'h2o':
    h2o_model_type = str(get_recipe_config()["H2O_Model_Type"])
    dia_license_table_name=""
    if h2o_model_type == 'h2o_dai':
        #For H2O-DAI, Fetching the License DB name from GUI
        dia_license_db_inputType = str(get_recipe_config()["H2O_DIALicense_DB"])
        if dia_license_db_inputType == 'user_license_db_choice':
            dia_license_db_name = str(get_recipe_config()["user_Typed_License_DB_Name"])
        elif dia_license_db_inputType == 'h2o_license_db_drop_down':
            dia_license_db_name = str(get_recipe_config()["H2OLicense_DropDown_DB_Name"])
            
        #For H2O-DAI, Fetching the License Table name from GUI
        dia_license_Table_inputType = str(get_recipe_config()["H2O_DIALicense_Table"])
        
        if dia_license_Table_inputType == 'user_license_table_choice':
            dia_license_table_name = str(get_recipe_config()["user_Typed_License_Table_Name"])
        elif dia_license_Table_inputType == 'h2o_license_table_drop_down':
            dia_license_table_name = str(get_recipe_config()["H2OLicense_DropDown_Table_Name"])

        
        if modeloutputfields_user == False:
            query = f"CREATE TABLE {verifyQualifiedTableName(outputDatabase, outputTable)} AS (SELECT * FROM {verifyDatabaseName(PMMLPredict_db)}.H2OPredict ( ON (select * from {verifyDatabaseName(database_name)}.{verifyDatabaseName(testing_dataset)}) AS InputTable ON (SELECT model_id, model, {verifyDatabaseName(dia_license_db_name)}.{verifyDatabaseName(dia_license_table_name)}.license FROM {verifyDatabaseName(database_name)}.{verifyTableName(table_name)} WHERE model_id = {verifyModelName(model_name)}) AS ModelTable DIMENSION USING {verifyAccumulate(accumulate)} ModelType ('DAI') {verifyOverwriteCache(overwrite_cache, model_name)})AS td) WITH DATA;"
        else:
            query = f"CREATE TABLE {verifyQualifiedTableName(outputDatabase, outputTable)} AS (SELECT * FROM {verifyDatabaseName(PMMLPredict_db)}.H2OPredict ( ON (select * from {verifyDatabaseName(database_name)}.{verifyDatabaseName(testing_dataset)}) AS InputTable ON (SELECT model_id, model, {verifyDatabaseName(dia_license_db_name)}.{verifyDatabaseName(dia_license_table_name)}.license FROM {verifyDatabaseName(database_name)}.{verifyTableName(table_name)} WHERE model_id = {verifyModelName(model_name)}) AS ModelTable DIMENSION USING {verifyAccumulate(accumulate)} ModelType ('DAI') {verifyModelOutputValues(modeloutputfields_values)} {verifyOverwriteCache(overwrite_cache, model_name)})AS td) WITH DATA;"
    else:
        if modeloutputfields_user == False:
            query = f"CREATE TABLE {verifyQualifiedTableName(outputDatabase, outputTable)} AS (SELECT * FROM {verifyDatabaseName(PMMLPredict_db)}.H2OPredict ( ON (select * from {verifyDatabaseName(database_name)}.{verifyDatabaseName(testing_dataset)}) AS InputTable ON (SELECT model_id, model FROM {verifyDatabaseName(database_name)}.{verifyTableName(table_name)} WHERE model_id = {verifyModelName(model_name)}) AS ModelTable DIMENSION USING {verifyAccumulate(accumulate)} {verifyOverwriteCache(overwrite_cache, model_name)})AS td) WITH DATA;"
        else:
            query = f"CREATE TABLE {verifyQualifiedTableName(outputDatabase, outputTable)} AS (SELECT * FROM {verifyDatabaseName(PMMLPredict_db)}.H2OPredict ( ON (select * from {verifyDatabaseName(database_name)}.{verifyDatabaseName(testing_dataset)}) AS InputTable ON (SELECT model_id, model FROM {verifyDatabaseName(database_name)}.{verifyTableName(table_name)} WHERE model_id = {verifyModelName(model_name)}) AS ModelTable DIMENSION USING {verifyAccumulate(accumulate)} {verifyModelOutputValues(modeloutputfields_values)} {verifyOverwriteCache(overwrite_cache, model_name)})AS td) WITH DATA;"
# Native dataiku scoring segment
if scoring_type == 'native':
    if modeloutputfields_user == False:
        query = f"CREATE TABLE {verifyQualifiedTableName(outputDatabase, outputTable)} AS (SELECT * FROM {verifyDatabaseName(PMMLPredict_db)}.DataikuPredict ( ON (select * from {verifyDatabaseName(database_name)}.{verifyDatabaseName(testing_dataset)}) AS InputTable ON (SELECT * FROM {verifyDatabaseName(database_name)}.{verifyTableName(table_name)} WHERE model_id = {verifyModelName(model_name)}) AS ModelTable DIMENSION USING {verifyAccumulate(accumulate)} {verifyOverwriteCache(overwrite_cache, model_name)})AS td) WITH DATA;"
    else:
        query = f"CREATE TABLE {verifyQualifiedTableName(outputDatabase, outputTable)} AS (SELECT * FROM {verifyDatabaseName(PMMLPredict_db)}.DataikuPredict ( ON (select * from {verifyDatabaseName(database_name)}.{verifyDatabaseName(testing_dataset)}) AS InputTable ON (SELECT * FROM {verifyDatabaseName(database_name)}.{verifyTableName(table_name)} WHERE model_id = {verifyModelName(model_name)}) AS ModelTable DIMENSION USING {verifyAccumulate(accumulate)} {verifyModelOutputValues(modeloutputfields_values)} {verifyOverwriteCache(overwrite_cache, model_name)})AS td) WITH DATA;"
# ONNX scoring segment
if scoring_type == 'onnx':
    if modeloutputfields_user == False:
        query = f"CREATE TABLE {verifyQualifiedTableName(outputDatabase, outputTable)} AS (SELECT * FROM {verifyDatabaseName(PMMLPredict_db)}.ONNXPredict ( ON (select * from {verifyDatabaseName(database_name)}.{verifyDatabaseName(testing_dataset)}) AS InputTable ON (SELECT * FROM {verifyDatabaseName(database_name)}.{verifyTableName(table_name)} WHERE model_id = {verifyModelName(model_name)}) AS ModelTable DIMENSION USING {verifyAccumulate(accumulate)} {verifyOverwriteCache(overwrite_cache, model_name)})AS td) WITH DATA;"
    else:
        query = f"CREATE TABLE {verifyQualifiedTableName(outputDatabase, outputTable)} AS (SELECT * FROM {verifyDatabaseName(PMMLPredict_db)}.ONNXPredict ( ON (select * from {verifyDatabaseName(database_name)}.{verifyDatabaseName(testing_dataset)}) AS InputTable ON (SELECT * FROM {verifyDatabaseName(database_name)}.{verifyTableName(table_name)} WHERE model_id = {verifyModelName(model_name)}) AS ModelTable DIMENSION USING {verifyAccumulate(accumulate)} {verifyModelOutputValues(modeloutputfields_values)} {verifyOverwriteCache(overwrite_cache, model_name)})AS td) WITH DATA;"


logging.info(f"Prediction Query ==> {query}")


query_band = "SET QUERY_BAND='org=teradata-internal-telem;appname=dataiku;version=4.1;" + "function= BYOM Scoring" + ";' FOR SESSION;"

# Execute the query
try:
    # dataiku's query_to_df's pre_query parameter seems to not work. This is a work-around to ensure that the 
    # "START TRANSACTION;" block applies for non-autocommit TERA mode connections.
    if not autocommit:
        executor.query_to_df(pre_query)
    logging.info('Setting queryband')
    executor.query_to_df(query_band)
    executor.query_to_df(query, post_queries=post_query)
except Exception as error:
    err_str = str(error)
    index = err_str.index("[Teradata Database]")
    if index != -1:
        err_str = err_str[index:]
    raise RuntimeError(err_str)

set_schema_from_vantage(outputTable, output_dataset, executor, post_query, autocommit, pre_query, outputDatabaseName=outputDatabase)

logging.info('Complete!')  

