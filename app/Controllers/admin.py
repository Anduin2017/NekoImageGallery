from pathlib import Path
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, params
from loguru import logger

from app.Models.admin_api_model import ImageOptUpdateModel
from app.Models.api_response.base import NekoProtocol
from app.Services import db_context
from app.Services.authentication import force_admin_token_verify
from app.Services.vector_db_context import PointNotFoundError
from app.config import config

admin_router = APIRouter(dependencies=[Depends(force_admin_token_verify)], tags=["Admin"])


@admin_router.delete("/delete/{image_id}",
                     description="Delete image with the given id from database. "
                                 "If the image is a local image, it will be moved to `/static/_deleted` folder.")
async def delete_image(
        image_id: Annotated[UUID, params.Path(description="The id of the image you want to delete.")]) -> NekoProtocol:
    try:
        point = await db_context.retrieve_by_id(str(image_id))
    except PointNotFoundError:
        raise HTTPException(404, "Cannot find the image with the given ID.")

    db_context.deleteItems([str(image_id)])
    logger.success("Image {} deleted from database.", image_id)

    if point.url.startswith('/'):  # local image
        static_folder = Path(config.static_file.path)
        image_files = list(static_folder.glob(f"{image_id}.*"))
        assert len(image_files) <= 1

        if len(image_files) == 0:
            logger.warning("Image {} is a local image but not found in static folder.", image_id)
        else:
            deleted_folder = static_folder / "_deleted"
            deleted_folder.mkdir(parents=True, exist_ok=True)

            image_files[0].rename(deleted_folder / image_files[0].name)
            logger.success("Local image {} removed.", image_files[0].name)

        if point.thumbnail_url is not None:
            thumbnail_dir = static_folder / "thumbnails"
            thumbnail_file = thumbnail_dir / f"{image_id}.webp"
            if thumbnail_file.is_file():
                thumbnail_file.unlink()
                logger.success("Thumbnail {} removed.", thumbnail_file.name)
            else:
                logger.warning("Thumbnail {} not found.", thumbnail_file.name)

    return NekoProtocol(message="Image deleted.")


@admin_router.put("/update_opt/{image_id}", description="Update a image's optional information")
async def update_image(image_id: Annotated[UUID, params.Path(description="The id of the image you want to delete.")],
                       model: ImageOptUpdateModel) -> NekoProtocol:
    if model.starred is None:
        raise HTTPException(422, "Nothing to update.")
    try:
        point = await db_context.retrieve_by_id(str(image_id))
    except PointNotFoundError:
        raise HTTPException(404, "Cannot find the image with the given ID.")

    if model.starred is not None:
        point.starred = model.starred

    await db_context.updatePayload(point)
    logger.success("Image {} updated.", image_id)

    return NekoProtocol(message="Image updated.")
