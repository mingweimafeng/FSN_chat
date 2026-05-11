from __future__ import annotations

import logging

logger = logging.getLogger(__name__)

SERVICE_NAME = "FSN_Chat"
ACCOUNT_NAME = "api_key"

_keyring_available: bool | None = None


def _check_keyring() -> bool:
    global _keyring_available
    if _keyring_available is not None:
        return _keyring_available
    try:
        import keyring  # noqa: F401
        _keyring_available = True
    except ImportError:
        logger.info("keyring 未安装，API 密钥将仅存储在配置文件中。执行 pip install keyring 以启用系统密钥库存储。")
        _keyring_available = False
    return _keyring_available


def store_api_key(api_key: str) -> None:
    if not _check_keyring():
        return
    import keyring
    try:
        if api_key:
            keyring.set_password(SERVICE_NAME, ACCOUNT_NAME, api_key)
        else:
            try:
                keyring.delete_password(SERVICE_NAME, ACCOUNT_NAME)
            except keyring.errors.PasswordDeleteError:
                pass
    except Exception as e:
        logger.warning("无法使用系统密钥库存储 API 密钥: %s", e)


def retrieve_api_key() -> str:
    if not _check_keyring():
        return ""
    import keyring
    try:
        return keyring.get_password(SERVICE_NAME, ACCOUNT_NAME) or ""
    except Exception as e:
        logger.warning("无法从系统密钥库读取 API 密钥: %s", e)
        return ""
