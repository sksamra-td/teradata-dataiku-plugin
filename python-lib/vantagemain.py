# -*- coding: utf-8 -*-
'''
Copyright © 2019 by Teradata.
Permission is hereby granted, free of charge, to any person obtaining a copy of this software and
associated documentation files (the "Software"), to deal in the Software without restriction,
including without limitation the rights to use, copy, modify, merge, publish, distribute,
sublicense, and/or sell copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:
The above copyright notice and this permission notice shall be included in all copies or
substantial portions of the Software.
THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR IMPLIED, INCLUDING BUT
NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE AND
NONINFRINGEMENT. IN NO EVENT SHALL THE AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM,
DAMAGES OR OTHER LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE SOFTWARE.
'''


# Pretty-printing of Dictionaries.
import pprint
import logging
import json
import time
import dataiku
from dataiku import Dataset
from dataiku.customrecipe import *
from dataiku.core.sql import SQLExecutor2
import pandas as pd

# Import plugin libs
from querybuilderfacade import *
from inputtableinfo import *
from outputtableinfo import *
import auth

# SQLE functions via Open ended query generation
from open_ended_query_generator import OpenEndedQueryGenerator
from vantage_schema import set_schema_from_vantage

# Valib functions
from teradata_valib import *


def vantageDo():

    """
    Takes the parameters set by the user from the UI, creates the query, and then executes it.
    """
    # Formatting options.
    SEP_LENGTH = 80
    SEP = "=" * SEP_LENGTH
    pp = pprint.PrettyPrinter(indent=4)
    
    # Recipe inputs
    main_input_name = get_input_names_for_role('main')[0]
    input_dataset = dataiku.Dataset(main_input_name)

    # Recipe outputs
    main_output_name = get_output_names_for_role('main')[0]
    output_dataset =  dataiku.Dataset(main_output_name)
    
    # Daitaiku DSS params
    client = dataiku.api_client()
    projectkey = main_input_name.split('.')[0]
    project = client.get_project(projectkey)
    connections = {}
    recipe_config = get_recipe_config()

    # Datasets
    input_table_names = []
    output_table_names = []
    # Get the Input Tables/Schema's
    try:
        # Map dataset names to table names
        inputtables = {}
        inputschemas = {}
        datasetnames = {}
        input_names = get_input_names()
        for input_name in input_names:
            inputDataset = dataiku.Dataset(input_name)
            user_table_name = input_name.split('.')[1]
            connectionInfo = inputDataset.get_location_info()['info']
            inputConnectionName = connectionInfo['connectionName']
            connections = auth.addConnection(connections, inputConnectionName)
            defaultDatabase = inputDataset.get_config()['params'].get('schema', '')
            if not defaultDatabase and inputConnectionName in connections:
                defaultDatabase = connections[inputConnectionName]['params']['defaultDatabase']
            full_table_name = connectionInfo['table']
            inputtables[user_table_name] = full_table_name
            inputschemas[user_table_name] = defaultDatabase
            datasetnames[user_table_name] = input_name
        recipe_config["function"]["inputtables"] = inputtables
        recipe_config["function"]["inputschemas"] = inputschemas

        # generate parameter inputs tables map: name, datasetName, table and schema
        required_inputs = recipe_config["function"]["required_input"]
        for required_input in required_inputs:
            user_table_name = ""
            if "value" in required_input:
                user_table_name = required_input["value"]
            if user_table_name == "":
                if ("isRequired" in required_input) and required_input["isRequired"]:
                    raise RuntimeError("Input is missing - " + required_input["name"])
                # No input set by user, so keep empty
                input_table_names.append({})
                continue
            full_table_name = inputtables[user_table_name]
            defaultDatabase = inputschemas[user_table_name]
            table_map = {}
            table_map["name"] = user_table_name
            table_map["table"] = full_table_name
            table_map["schema"] = defaultDatabase
            table_map["datasetName"] = datasetnames[user_table_name]
            input_table_names.append(table_map)
        recipe_config["function"]["input_table_names"] = input_table_names
    except Exception as error:
        # Allow Plot to have empty input tables
        if recipe_config.get('function', {}).get('name','') != "TD_PLOT":
            raise RuntimeError("""Error obtaining connection settings from one of the input tables."""                           
                           """This plugin only supports Teradata tables. Specify a default database name in your Teradata connection or a Schema in the input table connection settings.""")

    # Get the Output Tables/Schema's
    try:
        # generate parameter output tables map: name, datasetName, table and schema
        for output_name in get_output_names_for_role('main'):
            outputDataset = dataiku.Dataset(output_name)
            user_table_name = output_name.split('.')[1]
            connectionInfo = outputDataset.get_location_info()['info']
            outputConnectionName = connectionInfo['connectionName']
            connections = auth.addConnection(connections, outputConnectionName)
            defaultDatabase = outputDataset.get_config()['params'].get('schema', '')
            if not defaultDatabase and outputConnectionName in connections:
                defaultDatabase = connections[outputConnectionName]['params']['defaultDatabase']
            full_table_name = connectionInfo['table']
            table_map = {}
            table_map["name"] = user_table_name
            table_map["table"] = full_table_name
            table_map["schema"] = defaultDatabase
            table_map["datasetName"] = output_name
            output_table_names.append(table_map)
        recipe_config["function"]["output_table_names"] = output_table_names

    except Exception as error:
        raise RuntimeError("""Error obtaining connection settings from one of the input tables."""                           
                       """This plugin only supports Teradata tables. Specify a default database name in your Teradata connection or a Schema in the input table connection settings.""")

    
    # Connection properties.
    autocommit = True
    try:
        properties = input_dataset.get_location_info(sensitive_info=True)['info'].get('connectionParams').get('properties')
        autocommit = input_dataset.get_location_info(sensitive_info=True)['info'].get('connectionParams').get('autocommitMode')
    except:
        if inputConnectionName in connections:
            properties = connections[inputConnectionName]['params']['properties']
            autocommit = connections[inputConnectionName]['params']['autocommitMode']
        
    # SQL Executor.
    executor = SQLExecutor2(dataset=input_dataset)   
    
    # Handle pre- and post-query additions.
    # Assume autocommit TERA mode by default.
    pre_query = None
    post_query = None
    
    logging.info(SEP)
    if not autocommit:
        logging.info("NOT AUTOCOMMIT MODE.")
        logging.info("Assuming TERA mode.")
        pre_query = ["BEGIN TRANSACTION;"]
        post_query = ["END TRANSACTION;"]
        for prop in properties:
            if prop['name'] == 'TMODE':
                if prop['value'] == 'ANSI':
                    logging.info("ANSI mode.")
                    pre_query = [";"]
                    post_query = ["COMMIT WORK;"]
    
    else:
        logging.info("AUTOCOMMIT MODE.")
        logging.info("No pre- and post-query.")
    logging.info(SEP)

    # Recipe function param
    debug = False
    if debug:
        logging.info(SEP)
        logging.info('DSS Function:')
        logging.info(pp.pformat(dss_function))
        logging.info(SEP)

    logging.info(SEP)
    logging.info('get_recipe_config():')
    logging.info(pp.pformat(recipe_config))
    logging.info(SEP)

    # Add Query Band
    query_band = "SET QUERY_BAND='org=teradata-internal-telem;appname=dataiku;version=4.1;" + "function=" +  verifyAttribute(recipe_config.get('function', {}).get('name','')) + ";' FOR SESSION;"
    
    # VALIB     
    dss_function = recipe_config.get('function', None)
    if dss_function and 'function_type' in dss_function and dss_function['function_type'] == "valib":
        if pre_query:
            pre_query = [query_band] + pre_query
        else:
            pre_query = [query_band]
        dataiku_valib_execution(dss_function, connections, inputConnectionName, executor, autocommit, pre_query, post_query, output_table_names)
        return

    # --- AUTO ML SUPPORT ---
    # Define the updated consistent aliases from your JSONs
    automl_aliases = [
        'AutoClassifier_Fit', 
        'AutoClassifier_Predict', 
        'AutoRegressor_Fit',
        'AutoRegressor_Predict',
        'AutoChurn_Fit',
        'AutoChurn_Predict',
        'AutoFraud_Fit',
        'AutoFraud_Predict',
        'AutoCluster_Fit',
        'AutoCluster_Predict'
    ]

    current_alias = dss_function.get('function_alias_name')

    if current_alias in automl_aliases:
        import automl_handler
        logging.info(f"Routing {current_alias} to Python AutoML handler...")
        
        # Call the unified handler
        out_table, out_db = automl_handler.handle_autoclassifier(
            dss_function, 
            input_table_names, 
            output_table_names
        )
        
        # Sync schema back to Dataiku
        set_schema_from_vantage(
            out_table, 
            output_dataset, 
            executor, 
            post_query, 
            autocommit, 
            pre_query, 
            outputDatabaseName=out_db
        )
        return  # Exit to skip standard SQL execution

    # output dataset
    outputTable = output_table_names[0]["table"]
    outputDatabase = output_table_names[0].get("schema", "")
    # Handle dropping of output tables.
    if dss_function.get('dropIfExists', False):
        logging.info("Preparing to drop tables.")
        drop_query = dropTableStatement(outputTable, outputDatabase)
        
        logging.info(SEP)
        logging.info("DROP query:")
        logging.info(drop_query)
        logging.info(SEP)
        try:
            # dataiku's query_to_df's pre_query parameter seems to not work. This is a work-around to ensure that the 
            # "START TRANSACTION;" block applies for non-autocommit TERA mode connections.
            if not autocommit: 
                executor.query_to_df(pre_query)
            executor.query_to_df(drop_query, post_queries=post_query)
        except Exception as e:
            logging.info(e)
        
        # Drop other output tables if they exist.
        for tableIndex in range(1, len(output_table_names)):
            output_table_todrop = output_table_names[tableIndex]["table"]
            logging.info('Drop Additional Output Query:' + output_table_todrop)
            drop_query = DROP_QUERY.format(outputTablename=verifyTableName(output_table_todrop))
            try:
                if not autocommit: 
                    executor.query_to_df(pre_query)
                executor.query_to_df(drop_query, post_queries=post_query)
            except Exception as e:
                logging.info(e)


    # Create new query based on open ended approach
    sql_generator = OpenEndedQueryGenerator(outputTable, recipe_config, verbose=True, outputDatabaseName=outputDatabase)

    logging.info(SEP)
    logging.info("OpenEndedQueryGenerator query:")
    my_query = sql_generator.create_query()
    logging.info(my_query)
    logging.info(SEP)

        
    # Detect error
    try:
        # dataiku's query_to_df's pre_query parameter seems to not work. This is a work-around to ensure that the 
        # "START TRANSACTION;" block applies for non-autocommit TERA mode connections.
        if not autocommit:
            executor.query_to_df(pre_query)
        executor.query_to_df(my_query, pre_queries=[query_band], post_queries=post_query)
    except pd.errors.EmptyDataError:
        # Ignore error
        pass
    except Exception as error:
        # Ignore UAF errors as these indicate an empty table
        err_str = str(error)
        # Cleanup error , remove messages before "[Teradata Database]"
        if "[Teradata Database]" in err_str:
            index = err_str.index("[Teradata Database]")
            if index != -1:
                err_str = err_str[index:]
        raise RuntimeError(err_str)

    logging.info('Moving results to output...')

    # Call method for mapping Teradata types to the Dataiku types needed
    set_schema_from_vantage(outputTable, output_dataset, executor, post_query, autocommit, pre_query, outputDatabaseName=outputDatabase)
    # Additional Tables
    outtables = dss_function.get('output_tables', [])
    if(outtables != []):
        tableCounter = 1
        logging.info('Working on additional output tables')
        for output_index in range(1,len(output_table_names)):
            output_dataset2 =  dataiku.Dataset(output_table_names[output_index]["datasetName"]) 
            set_schema_from_vantage(output_table_names[output_index]["table"], output_dataset2, executor, post_query, autocommit, pre_query, outputDatabaseName=output_table_names[output_index].get("schema", ""))
            tableCounter += 1

    logging.info('Complete!')  


# Uncomment end