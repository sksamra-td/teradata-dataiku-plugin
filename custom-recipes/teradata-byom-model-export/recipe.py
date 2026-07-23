import dataiku
# Importing helpers for custom recipes
from dataiku.customrecipe import *
from teradatabyomtest import handle_models
import json
import logging
from verifyTableColumns import *
import auth
import pandas as pd, numpy as np
from dataiku import pandasutils as pdu

# Read recipe inputs

valid_connection = 1
client = dataiku.api_client()
# Obtiaining input name and project names.
in_name = get_input_names_for_role("source")[0]
project_name = in_name.split(".")[0]
input_name = in_name.split(".")[-1]
sourcetype = handle_models.get_input_object(str(input_name),str(project_name))

# Eliciting input information.
logging.info(sourcetype)

if sourcetype == 'model':
    model = dataiku.Model(get_input_names_for_role('source')[0])
    logging.info('=========================== MODEL')
    logging.info(model)
    # get whatever information you need from your model here
    
    model_def = model.get_definition()
    logging.info('================================ DEFINITION')
    logging.info(model_def)
    # view model definition 
    
    version_id = model_def.get('activeVersion')
    logging.info('======================================== Version ID')
    logging.info(version_id)
    
    project_key = model_def.get('projectKey')
    logging.info('======================================== Project Key')
    logging.info(project_key)
    
    saved_model_id = model_def.get('id')
    logging.info('======================================== Saved Model ID')
    logging.info(saved_model_id)
if sourcetype == 'folder':
    folder = dataiku.Folder(get_input_names_for_role('source')[0])
    logging.info('=========================== FOLDER')
    logging.info(folder)

    logging.info('================================ DEFINITION')
    logging.info(folder.get_info())

    logging.info('======================================== PATH')
    logging.info(folder.get_info().get("path"))

    logging.info('======================================== Folder ID')
    logging.info(folder.get_info().get("id"))



connection_name_raw = get_recipe_config()["connection_name"]
if not connection_name_raw:
    raise Exception("No Vantage connection selected. Please add a connection in the recipe settings.")
connection_name = str(connection_name_raw[0]) if isinstance(connection_name_raw, list) else str(connection_name_raw)
dss_connection_prams = client.get_connection(name=connection_name).get_info().get_params()

connection_info = client.get_connection(name=connection_name).get_info()
# reverted back to previous way of accessing user and password param
# fixes accessing connection credentials for “per-user” credentials mode 
user_param = str(connection_info.get_basic_credential()['user'])
#user_param = str(dss_connection_prams['user'])
logging.info(user_param)
    
host_param = str(dss_connection_prams['host'])
logging.info(host_param)
    
#password_param = str(dss_connection_prams['password'])
password_param = str(connection_info.get_basic_credential()['password']) 

database_param_by_user = str(get_recipe_config()["database_existing"])
if database_param_by_user == "":
   database_param = str(dss_connection_prams['defaultDatabase'])
else:
   database_param = database_param_by_user
    
properties_string = json.dumps(dss_connection_prams['properties'])

if 'logmech' and 'ldap' in properties_string.lower():
   logmech_param = 'LDAP'
elif 'logmech' and 'jwt' in properties_string.lower():
     logmech_param = 'JWT'
elif 'logmech' and 'krb5' in properties_string.lower():
     logmech_param = 'KRB5'
elif 'logmech' and 'tdnego' in properties_string.lower():
     logmech_param = 'TDNEGO'
else:
     logmech_param = 'TD2'
logging.info('======================================== EXISTING LDAP')
logging.info(logmech_param)

#encryption_param = "false"
#if bool(get_recipe_config()["encryption"]):
#    encryption_param = "true"

create_new_table_param = bool(get_recipe_config()["create"])
table_name_param = str(get_recipe_config()["tablename"])
modelname_param = str(get_recipe_config()["modelname"])
modeltype_param = str(get_recipe_config()["exporttype"])
# For optional parameters, you should provide a default value in case the parameter is not present:
#my_variable = get_recipe_config().get('parameter_name', None)

# Note about typing:
# The configuration of the recipe is passed through a JSON object
# As such, INT parameters of the recipe are received in the get_recipe_config() dict as a Python float.
# If you absolutely require a Python int, use int(get_recipe_config()["my_int_param"])


#############################
# Your original recipe
#############################

# -*- coding: utf-8 -*-

import sqlalchemy
#creating connection
connection_text = 'teradatasql://whomooz/?user={}&password={}&host={}&database={}&logmech={}'
connection_text = connection_text.format(user_param,password_param,host_param,database_param,logmech_param)
#connection_text = connection_text.format(user_param,password_param,host_param,database_param,logmech_param, encryption_param)
eng = sqlalchemy.create_engine(connection_text)

if valid_connection == 1:
    if (create_new_table_param == True):
        #delete_table_if_exists = f"DROP TABLE \"{table_name_param}\";"
        #eng.execute(delete_table_if_exists)
        create_table = f"CREATE SET TABLE {verifyDatabaseName(database_param)}.{verifyTableName(table_name_param)} (model_id VARCHAR (30), model BLOB ) PRIMARY INDEX (model_id);"
        delete_table_if_exists = f"DROP TABLE {verifyDatabaseName(database_param)}.{verifyTableName(table_name_param)};"
        try:
            with eng.connect() as conn:
                conn.execute(sqlalchemy.text(create_table))
        except Exception as e:
            logging.info("FAIL " + create_table)
            with eng.connect() as conn:
                try:
                    conn.execute(sqlalchemy.text(delete_table_if_exists))
                except Exception as e:
                    logging.info("FAIL " + delete_table_if_exists)
                conn.execute(sqlalchemy.text(create_table))

        delete_record_if_exists = f"delete from {verifyDatabaseName(database_param)}.{verifyTableName(table_name_param)} where model_id = {verifyModelName(modelname_param)};"
    else:
        delete_record_if_exists = f"delete from {verifyDatabaseName(database_param)}.{verifyTableName(table_name_param)} where model_id = {verifyModelName(modelname_param[0:30])};"
        try:
            with eng.connect() as conn:
                conn.execute(sqlalchemy.text(delete_record_if_exists))
        except Exception as e:
            logging.info("FAIL " + delete_record_if_exists)


insert_model = f"insert into {verifyDatabaseName(database_param)}.{verifyTableName(table_name_param)} (model_id, model) values(:model_id,:model);"

if modeltype_param=='pmml':
    model_data = client.get_project(project_key).get_saved_model(saved_model_id).get_version_details(version_id).get_scoring_pmml_stream().content    

elif modeltype_param=='native':
    model_data = client.get_project(project_key).get_saved_model(saved_model_id).get_version_details(version_id).get_scoring_jar_stream(include_libs=True).content

elif modeltype_param=='onnx':
    if sourcetype == 'model':
        model_data = client.get_project(project_key).get_saved_model(saved_model_id).get_version_details(version_id).get_scoring_artifact_stream("model.onnx").content
    else:
        file = str(get_recipe_config()["files"])
        with folder.get_download_stream(file) as stream:
            model_data = stream.read()

elif modeltype_param=='h2o':
    # Initially the name of the file is given to 'file' then iterated over the existing paths to see if a path name contains the file name,
    # if true it is obtained as a byte stream and uploaded else a error is raised.
    file = str(get_recipe_config()["files"])
    with folder.get_download_stream(file) as stream:
            model_data = stream.read()

parameters = {"model_id": modelname_param, "model": model_data}
try:
    with eng.connect() as conn:
        conn.execute(sqlalchemy.text(insert_model), parameters)
except Exception as e:
    print(str(e))

output_dataset_name = get_output_names_for_role('output_dataset')[0]
output_dataset = dataiku.Dataset(output_dataset_name) 
if valid_connection == 1:
    lst = [f"Successfully inserted model_id:{verifyModelName(modelname_param[0:30])} into Vantage Table {verifyDatabaseName(database_param)}.{verifyTableName(table_name_param)}"]
else:
    lst = ["Recipe failed. Specify valid Vantage connection."]
df = pd.DataFrame(lst)
output_dataset.write_with_schema(df)