# -*- coding: utf-8 -*-
import logging
import time
import dataiku
import json
import sqlalchemy
from dataiku.customrecipe import get_input_names_for_role
from sqlalchemy import MetaData
from teradataml import DataFrame, create_context, execute_sql, remove_context
from teradataml import AutoClassifier, AutoRegressor, AutoFraud, AutoCluster

# --- ROBUST MONKEY PATCH START ---
original_metadata_init = MetaData.__init__

def patched_metadata_init(self, *args, **kwargs):
    new_args = list(args)
    if new_args and not isinstance(new_args[0], (str, type(None))):
        if 'bind' not in kwargs:
            kwargs['bind'] = new_args.pop(0)
        else:
            new_args.pop(0)
    kwargs.pop('bind', None)
    return original_metadata_init(self, *tuple(new_args), **kwargs)

MetaData.__init__ = patched_metadata_init
# --- ROBUST MONKEY PATCH END ---

def handle_autoclassifier(dss_function, input_table_names, output_table_names):
    """
    Unified handler for AutoClassifier, AutoRegressor, AutoChurn, and AutoFraud (Fit and Predict).
    Dynamically retrieves credentials from Dataiku connection and maps UI 'Algorithm' to 'include'.
    """
    func_alias = dss_function.get('function_alias_name', '')
    logging.info(f"Routing execution to: {func_alias}")
    
    # --- DYNAMIC CONNECTION LOGIC ---
    client = dataiku.api_client()
    main_input_name = get_input_names_for_role('main')[0]
    input_dataset = dataiku.Dataset(main_input_name)
    
    connection_name = input_dataset.get_config().get("params", {}).get("connection")
    connection_info = client.get_connection(name=connection_name).get_info()
    dss_params = connection_info.get_params()
    
    host_param = str(dss_params.get('host', ''))
    user_param = str(connection_info.get_basic_credential().get('user', ''))
    password_param = str(connection_info.get_basic_credential().get('password', ''))
    
    # --- SETUP OUTPUT INFO ---
    output_table = output_table_names[0]["table"]
    output_database = output_table_names[0].get("schema", "")
    
    # --- INITIALIZE CONTEXT ---
    create_context(host=host_param, user=user_param, password=password_param)
    execute_sql("SET QUERY_BAND=NONE FOR SESSION;")
    if output_database:
        execute_sql(f"DATABASE {output_database};")

    # --- PARSE UI ARGUMENTS ---
    args_list = dss_function.get('arguments', [])
    params = {arg.get('name'): (None if arg.get('value') in ['', [''], []] else arg.get('value')) for arg in args_list}

    start_time = time.time()
    try:
        # --- FIT PATHS (Classifier, Regressor, Churn, Fraud) ---
        if func_alias in ['AutoClassifier_Fit', 'AutoRegressor_Fit', 'AutoChurn_Fit', 'AutoFraud_Fit', 'AutoCluster_Fit']:
            input_info = input_table_names[0]
            df_id = f'"{input_info.get("schema")}"."{input_info.get("table")}"' if input_info.get("schema") else input_info.get("table")
            
            kwargs = {}
            
            # CONSISTENT MAPPING: UI 'Algorithm' -> Backend 'include'
            if params.get('Algorithm') is not None: 
                kwargs['include'] = list(params.get('Algorithm'))
            
            # Common Parameters
            if params.get('Persist') is not None: kwargs['persist'] = bool(params.get('Persist'))
            if params.get('MaxRuntimeSecs') is not None: kwargs['max_runtime_secs'] = int(params.get('MaxRuntimeSecs'))
            if params.get('Verbose') is not None: kwargs['verbose'] = int(params.get('Verbose'))
            if params.get('StoppingMetric') is not None: kwargs['stopping_metric'] = str(params.get('StoppingMetric'))
            if params.get('StoppingTolerance') is not None: kwargs['stopping_tolerance'] = float(params.get('StoppingTolerance'))
            if params.get('MaxModels') is not None: kwargs['max_models'] = int(params.get('MaxModels'))
            if params.get('Seed') is not None: kwargs['seed'] = int(params.get('Seed'))
            if params.get('EnableLasso') is not None: kwargs['enable_lasso'] = bool(params.get('EnableLasso'))
            if params.get('RaiseErrors') is not None: kwargs['raise_errors'] = bool(params.get('RaiseErrors'))
            
            # Instance Handling (Fraud and Churn use AutoClassifier)
            if func_alias in ['AutoClassifier_Fit', 'AutoChurn_Fit', 'AutoFraud_Fit']:
                if params.get('ImbalanceHandlingMethod') is not None: 
                    kwargs['imbalance_handling_method'] = str(params.get('ImbalanceHandlingMethod'))
                automl = AutoClassifier(**kwargs)
            elif func_alias == 'AutoCluster_Fit':
                automl = AutoCluster(**kwargs)
            else: 
                automl = AutoRegressor(**kwargs)
            
            # Set cross-validation splits
            automl.cv_params = {'n_splits': 3} 
            
            logging.info(f"STARTING FIT: {func_alias} on {df_id}")
            train_df = DataFrame(df_id)
            automl.fit(train_df, target_column=params.get('TargetColumn'))
            
            logging.info(f"DEPLOYING MODEL to: {output_table}")
            automl.deploy(output_table)

        # --- PREDICT PATHS (Classifier, Regressor, Churn, Fraud) ---
        elif func_alias in ['AutoClassifier_Predict', 'AutoRegressor_Predict', 'AutoChurn_Predict', 'AutoFraud_Predict', 'AutoCluster_Predict']:
            data_id = f'"{input_table_names[0].get("schema")}"."{input_table_names[0].get("table")}"' if input_table_names[0].get("schema") else input_table_names[0].get("table")
            model_id = f'"{input_table_names[1].get("schema")}"."{input_table_names[1].get("table")}"' if input_table_names[1].get("schema") else input_table_names[1].get("table")
            
            try:
                rank_val = int(params.get('Rank', 1))
            except (TypeError, ValueError):
                rank_val = 1
                
            predict_kwargs = {'rank': rank_val}
            
            if params.get('PreserveColumns') is not None:
                predict_kwargs['preserve_columns'] = bool(params.get('PreserveColumns'))
            if params.get('UseLoadedModels') is not None:
                predict_kwargs['use_loaded_models'] = bool(params.get('UseLoadedModels'))
            
            # Routing logic
            if "Regressor" in func_alias:
                automl = AutoRegressor()
            elif "Cluster" in func_alias:
                automl = AutoCluster()
            else:
                automl = AutoClassifier()
            
            # --- KEEPING YOUR ORIGINAL LOGGING AND EXPLICIT DF ---
            logging.info(f"LOADING MODEL from: {model_id}")
            automl.load(model_id)
            
            logging.info(f"PREDICTING with Rank: {rank_val}")
            test_df = DataFrame(data_id)
            result_df = automl.predict(test_df, **predict_kwargs)
            result_df.to_sql(output_table, if_exists='replace')

        logging.info(f"{func_alias} completed in {time.time() - start_time:.2f} seconds.")

    except Exception as e:
        logging.error(f"AutoML error in {func_alias}: {str(e)}")
        raise
    finally:
        logging.info("Removing teradataml context...")
        remove_context()
    
    return output_table, output_database