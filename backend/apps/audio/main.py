import os
import logging
from fastapi import (
    FastAPI,
    Request,
    Depends,
    HTTPException,
    status,
    UploadFile,
    File,
    Form,
)
from fastapi.middleware.cors import CORSMiddleware
from faster_whisper import WhisperModel

from constants import ERROR_MESSAGES
from utils.utils import (
    decode_token,
    get_current_user,
    get_verified_user,
    get_admin_user,
)
from utils.misc import calculate_sha256

from config import (
    SRC_LOG_LEVELS,
    CACHE_DIR,
    UPLOAD_DIR,
    WHISPER_MODEL,
    WHISPER_MODEL_DIR,
    WHISPER_MODEL_AUTO_UPDATE,
    DEVICE_TYPE,
)

log = logging.getLogger(__name__)
log.setLevel(SRC_LOG_LEVELS["AUDIO"])

app = FastAPI()
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# setting device type for whisper model
whisper_device_type = DEVICE_TYPE if DEVICE_TYPE and DEVICE_TYPE == "cuda" else "cpu"
log.info(f"whisper_device_type: {whisper_device_type}")


@app.post("/transcribe")
def transcribe(
    file: UploadFile = File(...),
    user=Depends(get_current_user),
):
    log.info(f"file.content_type: {file.content_type}")

    if file.content_type not in ["audio/mpeg", "audio/wav"]:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=ERROR_MESSAGES.FILE_NOT_SUPPORTED,
        )

    try:
        filename = file.filename
        file_path = f"{UPLOAD_DIR}/{filename}"
        contents = file.file.read()
        with open(file_path, "wb") as f:
            f.write(contents)
            f.close()

        whisper_kwargs = {
            "model_size_or_path": WHISPER_MODEL,
            "device": whisper_device_type,
            "compute_type": "int8",
            "download_root": WHISPER_MODEL_DIR,
            "local_files_only": not WHISPER_MODEL_AUTO_UPDATE,
        }

        log.debug(f"whisper_kwargs: {whisper_kwargs}")

        try: 
            model = WhisperModel(**whisper_kwargs)
        except:
            log.debug("WhisperModel initialization failed, attempting download with local_files_only=False")
            whisper_kwargs["local_files_only"] = False
            model = WhisperModel(**whisper_kwargs)

        segments, info = model.transcribe(file_path, beam_size=5)
        log.info(
            "Detected language '%s' with probability %f"
            % (info.language, info.language_probability)
        )

        transcript = "".join([segment.text for segment in list(segments)])

        return {"text": transcript.strip()}

    except Exception as e:
        log.exception(e)

        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=ERROR_MESSAGES.DEFAULT(e),
        )
