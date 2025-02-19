import os
import shutil
import subprocess
import sys
import boto3
import click
from pathlib import Path
import tempfile
import json


@click.group()
def cli():
    """Deploy Lambda functions to AWS"""
    pass


@cli.command()
@click.option('--profile', default=None, help='AWS profile to use')
@click.option('--region', default='us-east-1', help='AWS region to deploy to')
@click.option('--function-name', required=True, help='Name of the Lambda function')
@click.option('--role-arn', required=True, help='ARN of the IAM role for Lambda')
@click.option('--source-dir', default='./src', help='Directory containing source files')
@click.option('--requirements-file', default='./requirements.txt', help='Path to requirements.txt')
@click.option('--python-version', default='3.11', help='Python version for Lambda runtime')
def deploy(profile, region, function_name, role_arn, source_dir, requirements_file, python_version):
    """Package and deploy the Lambda function"""
    try:
        # Set up AWS session
        session = boto3.Session(profile_name=profile, region_name=region)
        lambda_client = session.client('lambda')

        # Create temporary directory for packaging
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            click.echo(f"Created temporary directory: {temp_dir}")

            # Install dependencies
            click.echo("Installing dependencies...")
            subprocess.run([
                sys.executable,
                '-m',
                'pip',
                'install',
                '--target',
                str(temp_path),
                '-r',
                requirements_file
            ], check=True)

            # Copy source files to root level
            click.echo("Copying source files...")
            src_path = Path(source_dir)
            if src_path.is_dir():
                # Copy all Python files from src to root level
                for file in src_path.glob('*.py'):
                    click.echo(f"Copying {file} to root level")
                    shutil.copy2(file, temp_path)

            click.echo("Files in deployment package:")
            for file in temp_path.glob('*.py'):
                click.echo(f"  {file.name}")

            # Create ZIP file
            zip_path = Path('lambda_deployment.zip')
            if zip_path.exists():
                zip_path.unlink()

            click.echo("Creating ZIP file...")
            shutil.make_archive('lambda_deployment', 'zip', temp_dir)

            # Check if function exists
            try:
                lambda_client.get_function(FunctionName=function_name)
                # Update existing function
                click.echo("Updating existing function...")
                with open('lambda_deployment.zip', 'rb') as zip_file:
                    lambda_client.update_function_code(
                        FunctionName=function_name,
                        ZipFile=zip_file.read()
                    )
            except lambda_client.exceptions.ResourceNotFoundException:
                # Create new function
                click.echo("Creating new function...")
                with open('lambda_deployment.zip', 'rb') as zip_file:
                    lambda_client.create_function(
                        FunctionName=function_name,
                        Runtime=f'python{python_version}',
                        Role=role_arn,
                        Handler='lambda_function.lambda_handler',
                        Code={'ZipFile': zip_file.read()},
                        Timeout=300,
                        MemorySize=512,
                        Environment={
                            'Variables': {
                                'DYNAMODB_TABLE_NAME': 'social_media_posts'
                            }
                        }
                    )

            # Wait for function update to complete
            click.echo("Waiting for function update to complete...")
            waiter = lambda_client.get_waiter('function_updated')
            waiter.wait(
                FunctionName=function_name,
                WaiterConfig={'Delay': 5, 'MaxAttempts': 30}
            )

            # Update function configuration
            click.echo("Updating function configuration...")
            lambda_client.update_function_configuration(
                FunctionName=function_name,
                Timeout=300,
                MemorySize=512,
                Environment={
                    'Variables': {
                        'DYNAMODB_TABLE_NAME': 'social_media_posts'
                    }
                }
            )

            # Wait for configuration update to complete
            click.echo("Waiting for configuration update to complete...")
            waiter.wait(
                FunctionName=function_name,
                WaiterConfig={'Delay': 5, 'MaxAttempts': 30}
            )

            click.echo(f"Successfully deployed {function_name}")

    except Exception as e:
        click.echo(f"Error: {str(e)}", err=True)
        sys.exit(1)
    finally:
        # Cleanup
        if Path('lambda_deployment.zip').exists():
            Path('lambda_deployment.zip').unlink()


@cli.command()
@click.option('--profile', default=None, help='AWS profile to use')
@click.option('--region', default='us-east-1', help='AWS region')
@click.option('--function-name', required=True, help='Name of the Lambda function')
def get_config(profile, region, function_name):
    """Get the current configuration of a Lambda function"""
    try:
        session = boto3.Session(profile_name=profile, region_name=region)
        lambda_client = session.client('lambda')

        response = lambda_client.get_function(FunctionName=function_name)
        config = response['Configuration']

        # Print relevant configuration details
        click.echo(json.dumps({
            'FunctionName': config['FunctionName'],
            'Runtime': config['Runtime'],
            'Handler': config['Handler'],
            'Timeout': config['Timeout'],
            'MemorySize': config['MemorySize'],
            'Environment': config.get('Environment', {}),
            'LastModified': config['LastModified']
        }, indent=2))

    except Exception as e:
        click.echo(f"Error: {str(e)}", err=True)
        sys.exit(1)


if __name__ == '__main__':
    cli()