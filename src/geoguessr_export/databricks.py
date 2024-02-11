import os

from loguru import logger


def get_env_variable(key: str) -> str:
    try:
        from pyspark.dbutils import DBUtils
        from pyspark.sql import SparkSession

        spark = SparkSession.builder.getOrCreate()
        dbutils = DBUtils(spark)

        logger.info("Running inside Databricks, using Databricks secrets for API tokens.")
        return dbutils.secrets.get(scope="api-keys", key=key)

    except ImportError:
        logger.info("Running outside Databricks, using environment variables for API tokens.")
        return os.environ.get(key)
