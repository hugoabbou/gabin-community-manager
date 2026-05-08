import os
import shutil
import tempfile
import requests as _req

_CLOUD_NAME = os.getenv("CLOUDINARY_CLOUD_NAME", "")

if _CLOUD_NAME:
    import cloudinary
    import cloudinary.uploader
    import cloudinary.api
    cloudinary.config(
        cloud_name=_CLOUD_NAME,
        api_key=os.getenv("CLOUDINARY_API_KEY", ""),
        api_secret=os.getenv("CLOUDINARY_API_SECRET", ""),
    )

_LIB = "gabin/library"
_ARC = "gabin/archive"
_EXTS = {".jpg", ".jpeg", ".png", ".webp"}


def cloud_enabled() -> bool:
    return bool(_CLOUD_NAME)


def _pub_id(filename: str, archive: bool = False) -> str:
    stem = os.path.splitext(filename)[0]
    return f"{_ARC if archive else _LIB}/{stem}"


def upload(data: bytes, filename: str) -> dict:
    if cloud_enabled():
        r = cloudinary.uploader.upload(
            data,
            folder=_LIB,
            public_id=os.path.splitext(filename)[0],
            resource_type="image",
            overwrite=True,
        )
        return {"url": r["secure_url"], "filename": filename}
    from backend.visuals import LIBRARY_DIR
    os.makedirs(LIBRARY_DIR, exist_ok=True)
    path = os.path.join(LIBRARY_DIR, filename)
    with open(path, "wb") as f:
        f.write(data)
    return {"url": f"assets/library/{filename}", "filename": filename}


def list_library() -> list:
    if cloud_enabled():
        try:
            r = cloudinary.api.resources(
                type="upload", prefix=_LIB + "/", max_results=100, resource_type="image"
            )
            return [
                {
                    "url": x["secure_url"],
                    "filename": x["public_id"].split("/")[-1] + "." + x.get("format", "jpg"),
                }
                for x in r.get("resources", [])
            ]
        except Exception:
            return []
    from backend.visuals import LIBRARY_DIR
    os.makedirs(LIBRARY_DIR, exist_ok=True)
    out = []
    for f in sorted(os.listdir(LIBRARY_DIR)):
        if f == "archive":
            continue
        if os.path.splitext(f)[1].lower() in _EXTS:
            out.append({
                "url": f"assets/library/{f}",
                "filename": f,
                "path": os.path.join(LIBRARY_DIR, f),
            })
    return out


def list_archive() -> list:
    if cloud_enabled():
        try:
            r = cloudinary.api.resources(
                type="upload", prefix=_ARC + "/", max_results=100, resource_type="image"
            )
            return [
                {
                    "url": x["secure_url"],
                    "filename": x["public_id"].split("/")[-1] + "." + x.get("format", "jpg"),
                }
                for x in r.get("resources", [])
            ]
        except Exception:
            return []
    from backend.visuals import LIBRARY_DIR
    arc_dir = os.path.join(LIBRARY_DIR, "archive")
    os.makedirs(arc_dir, exist_ok=True)
    out = []
    for f in sorted(os.listdir(arc_dir)):
        if os.path.splitext(f)[1].lower() in _EXTS:
            out.append({
                "url": f"assets/library/archive/{f}",
                "filename": f,
                "path": os.path.join(arc_dir, f),
            })
    return out


def delete(filename: str) -> None:
    if cloud_enabled():
        try:
            cloudinary.uploader.destroy(_pub_id(filename), resource_type="image")
        except Exception:
            pass
        return
    from backend.visuals import LIBRARY_DIR
    path = os.path.join(LIBRARY_DIR, filename)
    if os.path.exists(path):
        os.remove(path)


def archive_image(filename: str) -> None:
    if cloud_enabled():
        try:
            cloudinary.uploader.rename(
                _pub_id(filename), _pub_id(filename, archive=True), resource_type="image"
            )
        except Exception:
            pass
        return
    from backend.visuals import LIBRARY_DIR
    src = os.path.join(LIBRARY_DIR, filename)
    arc_dir = os.path.join(LIBRARY_DIR, "archive")
    os.makedirs(arc_dir, exist_ok=True)
    if os.path.exists(src):
        shutil.move(src, os.path.join(arc_dir, filename))


def restore_image(filename: str) -> None:
    if cloud_enabled():
        try:
            cloudinary.uploader.rename(
                _pub_id(filename, archive=True), _pub_id(filename), resource_type="image"
            )
        except Exception:
            pass
        return
    from backend.visuals import LIBRARY_DIR
    src = os.path.join(LIBRARY_DIR, "archive", filename)
    if os.path.exists(src):
        shutil.move(src, os.path.join(LIBRARY_DIR, filename))


def local_path_for(url: str) -> str:
    """Return a local file path for PIL/AI. Downloads from Cloudinary if needed."""
    if not cloud_enabled():
        # url is like "assets/library/foo.jpg" — convert to absolute path
        from backend.visuals import LIBRARY_DIR
        filename = url.split("/")[-1]
        return os.path.join(LIBRARY_DIR, filename)
    resp = _req.get(url, timeout=15)
    resp.raise_for_status()
    ext = "." + url.split("?")[0].split(".")[-1].lower() if "." in url.split("/")[-1] else ".jpg"
    tmp = tempfile.NamedTemporaryFile(delete=False, suffix=ext)
    tmp.write(resp.content)
    tmp.close()
    return tmp.name
