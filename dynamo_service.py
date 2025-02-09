import boto3
import logging
from typing import Dict, Any

logger = logging.getLogger()


class DynamoDBService:
    def __init__(self, table_name: str):
        self.table_name = table_name
        self.session = boto3.Session(profile_name='tradesales')
        self.create_table_if_not_exists()

    def create_table_if_not_exists(self):
        dynamodb = self.session.client('dynamodb')

        table_definition = {
            'TableName': self.table_name,
            'KeySchema': [
                {'AttributeName': 'PostId', 'KeyType': 'HASH'},
                {'AttributeName': 'PostDate', 'KeyType': 'RANGE'}
            ],
            'AttributeDefinitions': [
                {'AttributeName': 'PostId', 'AttributeType': 'S'},
                {'AttributeName': 'PostDate', 'AttributeType': 'S'}
            ],
            'ProvisionedThroughput': {
                'ReadCapacityUnits': 5,
                'WriteCapacityUnits': 5
            }
        }

        try:
            dynamodb.create_table(**table_definition)
            logger.info(f"Table '{self.table_name}' creation initiated")
        except dynamodb.exceptions.ResourceInUseException:
            logger.info(f"Table '{self.table_name}' already exists")
        except Exception as e:
            logger.error(f"Error creating table: {e}")

    def insert_item(self, post_date: str, post_id: str, summary: str, metadata: Dict[str, Any] = None) -> bool:
        try:
            table = self.session.resource('dynamodb').Table(self.table_name)
            item = {
                'PostDate': post_date,
                'PostId': post_id,
                'Summary': summary
            }
            if metadata:
                item['Metadata'] = metadata

            table.put_item(Item=item)
            return True
        except Exception as e:
            logger.error(f"Error inserting item: {e}")
            return False