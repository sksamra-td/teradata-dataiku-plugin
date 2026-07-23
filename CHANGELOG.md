# Teradata Plugin Changelog

# Versions 4.1.12 (eFix - July 2026)

* Bug fix: BYOM Model Export - Fixed a crash on page load caused by DSS 14.6 now triggering UI code for hidden parameters before the user has selected anything
* Bug fix: BYOM Model Export — Added a mandatory flag to the Vantage connection field to prevent running without a connection selected
* Bug fix: BYOM Scoring — Fixed a crash on page load for the same reason — hidden dropdown parameters being triggered before the user has filled in dependent fields


# Versions 4.0.12 (June 2026)

* Added over 10 new 17.20 functions
* Added AutoML predict and fit functions (AutoChurn_Fit, AutoChurn_Predict, AutoClassifier_Fit, AutoClassifier_Predict, AutoRegressor_Fit, AutoRegressor_Predict, AutoCluster_Fit, AutoCluster_Predict, AutoFraud_Fit, AutoFraud_Predict)
* Fixed Query band.


# Versions 3.4.11, 3.4.12 (eFix - May 2025)

* Removed Python version 3.8, plugin supports Python version 3.9 to 3.11.
* Bug fix: In-Vantage Scripting: Recipe uses the underlying table name regardless of what the overhead name of input table is called.
* Bug fix: BYOM export: Fix to support latest SQLAlchemy version.

# Versions 3.3.11, 3.3.12 (eFix - September 2024)

* Removed Python version 3.6 and 3.7, plugin supports Python version 3.8 to 3.11.
* Bug fix: In-Vantage Scripting (for VantageCloud Lake connections): On the APPLY Arguments screen, in “View details”, file names now displays correctly.
* Bug fix: In-Vantage Scripting: In arguments tab, the script language dropdown is now populated correctly.
* Bug fix: In-Vantage Scripting (for VantageCloud Enterprise and Vantage Core connections): UIF enabled systems now work correctly with new JDBC parameter ELICIT_FILE_PATH.
* Bug fix: In-Vantage Scripting: Non-admin users are now able to execute the recipe correctly.
* Bug fix: BYOM export: Accessing connection credentials for per-user credentials is fixed.
* In-Vantage Scripting (for VantageCloud Enterprise and Vantage Core connections), we no longer support uploading files through Vantage servers, only option is through Dataiku Managed Folder.

# Versions 3.2.11, 3.2.12 (eFix - May 2024)

* Bug fix: In-Vantage Scripting (VantageCLoud Lake): Dropdown menus are no longer affected by the user choice of Python interpreter version for the environment the plugin operates in.
* Bug fix: In-Vantage Scripting (VantageCLoud Lake): On the APPLY Arguments screen, variable type field tooltip in the Output Variables section now displays correctly.
* Bug fix: In-Vantage Scripting (VantageCLoud Lake): On the APPLY Arguments screen, the Nulls Listing field now correctly appears once regardless the number of partitioning columns.

# Versions 3.1.11, 3.1.12 (eFix - April 2024)

* Bug fix: In-Vantage Scripting (VantageCLoud Lake): Now correctly populates the dropdowns in 'User Environment' tab.
* Bug fix: Analytic functions recipe: The TD_RESAMPLE function fields reflect correctly the latest changes in the function definition. 
* In-Vantage Scripting (VantageCLoud Lake): The OAF authentication method has been upgraded to utilize PAT authentication. To authenticate, users now require a UES URL, a private key PEM file, and a PAT token.
* Support for monitoring telemetry data to enhance tracking capabilities.
* Analytic Functions now allow 'Order By' functionality for Dimension type.
* The Analytic Functions recipe UI now includes a note in the Decription field. For select functions, the note highlights a best-practice reminder about specifying the schema or database name for the input table.

## Versions 3.0.11, 3.0.12 (October 2023)

* This version fully supports connections to all Teradata Vantage systems (VantageCloud Lake, VantageCloud Enterprise, and Vantage Core.)
* New feature: The In-Vantage Scripting recipe has been expanded to include using the Open Analytics Framework and the APPLY Table Operator in VantageCloud Lake systems. The recipe adjusts to the corresponding suitable interface depending on the Teradata Vantage system type where the inputs reside.
* Support for ONNX and Dataiku native model formats in BYOM recipes.
* Minor updates to some of the Analytic Functions definition JSON files.

## Versions 2.3.11, 2.3.12 (July 2023)

* Dataiku 12 is incompatible with preceding Dataiku releases. This plugin release begins support for both Dataiku 11 (or older) and 12 (and newer) releases. For as long as the plugin supports concurrently these 2 different Dataiku release families, the plugin will be using the efix version number to designate compatibility with the corresponding Dataiku release family. To this end: Releasing distinct versions for Dataiku 11 or older (v.2.3.11) and Dataiku 12 (v.2.3.12) platforms. Version 2.3.0 is otherwise identical to 2.3.11.

## Version 2.3.0 (May 2023)

* Support for the Unbounded Array Framework (UAF) time series functions.
* Bug fix: BYOM recipes did not by default run queries in TERA mode.
* Bug fix: If the user should have inadequate permissions to access a recipe, the plugin no longer produces a generic "External Code Failed" error; a permissions-related message is now issued upon accessing a recipe, instead.

## Version 2.2.1 (eFix - February 2023)

* Bug fix: An issue prevented non-admin users from running plugin recipes.

## Version 2.2.0 (December 2022)

* Support for 54 new Analytic Functions in Analytics Database 17.20.
* Bug fix: BYOM scoring recipe: Performance improvement by directly routing the scoring output to the database.

## Version 2.1.2 (eFix - October 2022)

* Bug fix: Analytic functions recipe: A naming mismatch caused errors when executing functions that use the "Number Of Splits" argument.
* Bug fix: BYOM scoring recipe: Now correctly uses the name of a Vantage table to reference the testing Dataset instead of the Dataiku Dataset name.
* Bug fix: BYOM model export recipe: Now correctly addresses the scenario where a user might choose a connection whose credentials mode is “per user”.

## Version 2.1.1 (eFix - October 2022)

* Bug fix: Analytic Functions recipe: Output Dataset is now fully qualified with database so that it can be different from the input Dataset database.
* Bug fix: Analytic Functions recipe: Execution of VAL functions now takes place on the input Dataset server.

## Version 2.1.0 (August 2022)

* Support for VAL functions.
* Merging of Analytic and VAL functions into single recipe.
* Code refactoring in the Analytic Functions recipes.
* Renaming of "SCRIPT Table Operator Analysis" recipe into "In-Vantage Scripting".
* Bug fixes.

## Version 2.0.0 (June 2022)

* Integration of all former plugins into the unified Teradata plugin.
* Code refactoring in the Analytic Functions recipes.
* Bug fixes.
* Interface update for the SCRIPT Table Operator Analysis recipe.
* Alignment with Dataiku plugin development guidelines.

## Version 1.0.0 / 0.2.3 (December 2021)

* Initial release of BYOM recipes bundled as the former Teradata BYOM plugin for Dataiku.

## Version 0.2.2 (July 2021)

* First officially supported release; features the Teradata Analytics Database Functions and SCRIPT Table Operator plugins.