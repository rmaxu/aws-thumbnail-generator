import json
import boto3
import logging
import os
import yaml
from PIL import Image
from urllib.parse import unquote_plus

STAGE = os.getenv("stage")
INPUT_BUCKET = f"images-{STAGE}"
OUTPUT_BUCKET = f"thumbnails-{STAGE}"
logging.getLogger().setLevel(logging.INFO)
logger = logging.getLogger()
s3_client = boto3.client('s3')


def read_yml(path: str) -> dict:
    with open(path) as stream:
        return yaml.safe_load(stream)


def download_image(bucket, key):
    try:
        path = f"/tmp/{key.replace('/', '_')}"
        logger.info(f"Downloading image {key} into path {path}...")
        s3_client.download_file(bucket, key, path)
        return path
    except Exception as e:
        logger.error("Unable to download image!")
        raise e


def upload_image(bucket, key, path):
    try:
        logger.info(f"Uploading image {path} to {bucket}/{key}...")
        response = s3_client.upload_file(path, bucket, key)
        return response
    except Exception as e:
        logger.error("Unable to upload image!")
        raise e


def create_thumbnail(input_path, output_path, size):
    try:
        logger.info("Generating thumbnail...")
        with Image.open(input_path) as image:
            image.thumbnail((size.get("width"), size.get("height")))
            image.save(output_path)
        return {
            "message": "success!"
        }
    except Exception as e:
        logger.error("Could not generate thumbnail!")
        raise e


def handler(event, context):
    try:
        key = unquote_plus(event["Records"][0]['s3']['object']['key'], encoding="utf-8")
        config = read_yml("functions/config.yml")
        valid_formats = config.get("valid_formats")
        tmbsize = config.get("thumbnail-size")
        im_format = key.split(".")[-1]
        if im_format.lower() in valid_formats:
            download_path = download_image(INPUT_BUCKET, key)
            thumb_path = download_path.replace(im_format, "") + f"_thumbnail.{im_format}"
            create_thumbnail(download_path, thumb_path, tmbsize)
            key_out = download_path.replace(im_format, "") + f"_thumbnail.{im_format}"
            upload_image(OUTPUT_BUCKET, key_out, thumb_path)
            logger.info(f"Thumbnail created and uploaded to {OUTPUT_BUCKET}/{key_out} successfully!")
            body = {
                "success": True,
                "message": {
                    "thumbnail_uri": f"s3://{OUTPUT_BUCKET}/{key_out}"
                }
            }
        else:
            msg = "The image does not have a valid format!"
            logger.warning(msg)
            body = {
                "success": False,
                "message": msg
            }
        response = {
            "statusCode": 200,
            "body": json.dumps(body)
        }

    except Exception as e:
        logger.info(e)
        body = {
            "success": False,
            "message": f"{e}"
        }
        response = {
            "statusCode": 400,
            "body": json.dumps(body)
        }

    return response
