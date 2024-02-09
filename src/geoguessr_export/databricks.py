import os


def get_env_variable(key: str) -> str:
    try:
        from pyspark.dbutils import DBUtils
        from pyspark.sql import SparkSession

        spark = SparkSession.builder.getOrCreate()
        dbutils = DBUtils(spark)

        return dbutils.secrets.get(scope="api-keys", key=key)

    except ImportError:
        return os.environ.get(key)
