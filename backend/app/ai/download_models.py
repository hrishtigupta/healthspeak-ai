"""Download the local AI models (run once per computer).

From backend\\:
    ..\\.venv\\Scripts\\python.exe -m app.ai.download_models            # speech recognition (~1 GB)
    ..\\.venv\\Scripts\\python.exe -m app.ai.download_models --translation   # translation (gated, see below)

Files go to the Hugging Face cache (by default %USERPROFILE%\\.cache\\huggingface),
which is outside the project folder, so they are never committed or synced by OneDrive.

The IndicTrans2 translation models are "gated": first create a free Hugging Face
account, open the model page in a browser, accept its terms, then run
`huggingface-cli login` (or set HF_TOKEN) before using --translation.
"""

import argparse
import sys

from app.core.config import get_settings

ASR_PATTERNS = ["*.json", "*.txt", "model.safetensors"]
# IndicTrans2 ships its SentencePiece tokenizers as "model.SRC" / "model.TGT" (not "*.model").
TRANSLATION_PATTERNS = ["*.json", "*.txt", "*.py", "*.model", "model.SRC", "model.TGT", "model.safetensors"]


def _download(model_id: str, revision: str, patterns: list[str]) -> None:
    from huggingface_hub import snapshot_download
    from huggingface_hub.errors import GatedRepoError, HfHubHTTPError

    print(f"Downloading {model_id} @ {revision[:10]} ...")
    try:
        path = snapshot_download(model_id, revision=revision, allow_patterns=patterns)
    except GatedRepoError:
        print(f"  {model_id} is gated. Accept its terms at https://huggingface.co/{model_id} "
              "while logged in, then run `huggingface-cli login` and try again.")
        raise SystemExit(2) from None
    except HfHubHTTPError as exc:
        print(f"  Download failed: {exc}")
        raise SystemExit(1) from None
    print(f"  done: {path}")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--translation", action="store_true", help="also download the translation model")
    parser.add_argument("--translation-only", action="store_true", help="only the translation model")
    args = parser.parse_args(argv)
    try:
        import huggingface_hub  # noqa: F401
    except ImportError:
        print("Install backend/requirements-ai.txt first.")
        return 1
    s = get_settings()
    if not args.translation_only:
        _download(s.asr_model_id, s.asr_model_revision, ASR_PATTERNS)
    if args.translation or args.translation_only:
        _download(s.translation_model_id, s.translation_model_revision, TRANSLATION_PATTERNS)
    return 0


if __name__ == "__main__":
    sys.exit(main())
