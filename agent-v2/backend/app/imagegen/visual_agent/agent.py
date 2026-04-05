from __future__ import annotations

import logging
import textwrap
from pathlib import Path
from typing import Union

from google import genai
from google.genai import types

from ..config import get_settings, require_google_key

logger = logging.getLogger(__name__)

_client: genai.Client | None = None


def _get_client() -> genai.Client:
    global _client
    require_google_key()
    if _client is None:
        _client = genai.Client(api_key=get_settings().google_api_key)
    return _client


def _static_dir() -> Path:
    return get_settings().static_context_dir


def _temp_dir() -> Path:
    return get_settings().temporary_context_dir


def _read_text_files(directory: Path) -> list[str]:
    texts: list[str] = []
    if not directory.is_dir():
        return texts
    for path in sorted(directory.iterdir()):
        if path.suffix.lower() in {".md", ".txt"} and path.is_file():
            try:
                texts.append(path.read_text(encoding="utf-8"))
            except Exception as exc:
                logger.warning("Could not read %s: %s", path, exc)
    return texts


def _read_image_files(directory: Path) -> list[tuple[str, bytes]]:
    settings = get_settings()
    images: list[tuple[str, bytes]] = []
    if not directory.is_dir():
        return images
    for path in sorted(directory.iterdir()):
        if path.suffix.lower() in settings.image_extensions and path.is_file():
            try:
                images.append((path.name, path.read_bytes()))
            except Exception as exc:
                logger.warning("Could not read image %s: %s", path, exc)
    return images


def _mime_type(filename: str) -> str:
    ext = Path(filename).suffix.lower()
    return {
        ".png": "image/png",
        ".jpg": "image/jpeg",
        ".jpeg": "image/jpeg",
        ".webp": "image/webp",
        ".gif": "image/gif",
        ".bmp": "image/bmp",
    }.get(ext, "image/png")


def load_context(board_id: str | None = None) -> dict:
    settings = get_settings()
    static_dir = _static_dir()
    temp_dir = _temp_dir()
    style_texts = _read_text_files(static_dir)
    static_images = _read_image_files(static_dir)

    board_images: list[tuple[str, bytes]] = []
    if board_id:
        # Folder names use '__' in place of ':' (tldraw IDs contain colons
        # which are not valid in filesystem paths on some OSes).
        folder_name = board_id.replace(":", "__")
        board_dir = temp_dir / folder_name
        board_images = _read_image_files(board_dir)
        style_texts += _read_text_files(board_dir)

    return {
        "style_texts": style_texts,
        "static_images": static_images,
        "board_images": board_images,
    }


def _load_image_bytes(path: Union[str, Path]) -> bytes:
    return Path(path).read_bytes()


def _build_image_prompt(
    slide: dict,
    style_texts: list[str],
    extra_texts: list[str] | None = None,
    has_person_refs: bool = False,
) -> str:
    texts = slide.get("text_elements", {})
    palette = ", ".join(slide.get("color_palette", []))

    brand_block = ""
    if style_texts:
        merged = "\n\n---\n\n".join(style_texts)
        brand_block = "Brand & style guide (follow strictly):\n" + merged + "\n"

    face_instruction = ""
    if has_person_refs:
        face_instruction = (
            "IMPORTANT: The reference images above include real people. "
            "Preserve their exact facial appearance, skin tone, hair, and "
            "distinctive features faithfully in the generated image. "
            "Do NOT alter or replace the faces.\n"
        )

    extra_list = list(extra_texts or [])
    additional_context = (
        ("Additional context:\n" + "\n".join(extra_list)) if extra_list else ""
    )

    return textwrap.dedent(f"""
        Create a high-quality digital visual / slide for a presentation.

        Slide title: {slide.get('title', '')}
        Layout: {slide.get('layout', 'hero')}
        Visual description: {slide.get('visual_description', '')}
        Headline text (overlay): {texts.get('headline', '')}
        Body text (overlay): {texts.get('body', '')}
        Caption (overlay): {texts.get('caption', '')}
        Color palette: {palette}
        Overall style: {slide.get('overall_style', 'modern, clean, professional')}
        Mood: {slide.get('mood', 'inspiring')}

        {brand_block}
        {face_instruction}
        {additional_context}

        Use the provided reference images as visual templates for composition,
        color grading, and brand style. The image should be photorealistic or
        high-quality digital art, 16:9 widescreen, suitable for a professional
        presentation. Include the text elements as part of the visual design
        (typographic composition).
    """).strip()


def _generate_with_flash(
    prompt: str,
    reference_images: list[tuple[str, bytes]],
) -> bytes | None:
    settings = get_settings()
    client = _get_client()
    parts: list = []
    for fname, img_bytes in reference_images:
        parts.append(types.Part.from_bytes(data=img_bytes, mime_type=_mime_type(fname)))
    parts.append(types.Part.from_text(text=prompt))

    try:
        response = client.models.generate_content(
            model=settings.gemini_image_model,
            contents=[types.Content(role="user", parts=parts)],
            config=types.GenerateContentConfig(
                response_modalities=["IMAGE", "TEXT"],
                temperature=settings.visual_generation_temperature,
            ),
        )
        for part in response.candidates[0].content.parts:
            if part.inline_data is not None:
                return part.inline_data.data
    except Exception as exc:
        logger.warning("Flash image-gen failed: %s", exc)
    return None


def _generate_with_imagen(prompt: str) -> bytes | None:
    settings = get_settings()
    client = _get_client()
    try:
        response = client.models.generate_images(
            model=settings.imagen_model,
            prompt=prompt,
            config=types.GenerateImagesConfig(
                number_of_images=1,
                aspect_ratio=settings.visual_default_aspect_ratio,
            ),
        )
        return response.generated_images[0].image.image_bytes
    except Exception as exc:
        logger.warning("Imagen fallback failed: %s", exc)
    return None


def generate_one_slide_bytes(
    slide: dict,
    *,
    board_id: str | None = None,
    input_images: dict[str, Union[str, Path]] | None = None,
    extra_texts: list[str] | None = None,
    scenario_defaults: dict | None = None,
) -> bytes | None:
    """Generate one slide image in memory (no file write)."""
    input_images = input_images or {}
    extra_texts = extra_texts or []
    sd = scenario_defaults or {}
    slide = {**slide}
    slide.setdefault("overall_style", sd.get("overall_style", "modern, clean, professional"))
    slide.setdefault("mood", sd.get("mood", "inspiring"))

    ctx = load_context(board_id=board_id)
    style_texts = ctx["style_texts"]
    static_images = ctx["static_images"]
    board_images = ctx["board_images"]
    has_person_refs = len(board_images) > 0

    ref_images: list[tuple[str, bytes]] = []
    ref_images.extend(static_images)
    ref_images.extend(board_images)

    for fname in slide.get("images_to_use", []):
        if fname == "generate":
            continue
        if fname in input_images:
            try:
                ref_images.append((fname, _load_image_bytes(input_images[fname])))
            except Exception as exc:
                logger.warning("Could not load input image %s: %s", fname, exc)

    prompt = _build_image_prompt(
        slide,
        style_texts=style_texts,
        extra_texts=extra_texts,
        has_person_refs=has_person_refs,
    )

    img_bytes = _generate_with_flash(prompt, ref_images)
    if img_bytes is None:
        img_bytes = _generate_with_imagen(prompt)
    return img_bytes


def run(
    scenario: dict,
    board_id: str | None = None,
    input_images: dict[str, Union[str, Path]] | None = None,
    extra_texts: list[str] | None = None,
    output_dir: Union[str, Path] = "output_slides",
) -> list[Path]:
    input_images = input_images or {}
    extra_texts = extra_texts or []
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    ctx = load_context(board_id=board_id)
    style_texts = ctx["style_texts"]
    static_images = ctx["static_images"]
    board_images = ctx["board_images"]
    has_person_refs = len(board_images) > 0

    for slide in scenario.get("slides", []):
        slide.setdefault("overall_style", scenario.get("overall_style", "modern"))
        slide.setdefault("mood", scenario.get("mood", "inspiring"))

    generated: list[Path] = []

    for slide in scenario.get("slides", []):
        idx = slide.get("slide_number", len(generated) + 1)

        ref_images: list[tuple[str, bytes]] = []
        ref_images.extend(static_images)
        ref_images.extend(board_images)

        for fname in slide.get("images_to_use", []):
            if fname == "generate":
                continue
            if fname in input_images:
                try:
                    ref_images.append((fname, _load_image_bytes(input_images[fname])))
                except Exception as exc:
                    logger.warning("Could not load %s: %s", fname, exc)

        prompt = _build_image_prompt(
            slide,
            style_texts=style_texts,
            extra_texts=extra_texts,
            has_person_refs=has_person_refs,
        )

        img_bytes = _generate_with_flash(prompt, ref_images)
        if img_bytes is None:
            img_bytes = _generate_with_imagen(prompt)

        if img_bytes is None:
            logger.error("Could not generate slide %s", idx)
            continue

        out_path = output_dir / f"slide_{idx:02d}.png"
        out_path.write_bytes(img_bytes)
        generated.append(out_path)

    return generated
