"""Compat shims for modern Telegram Desktop tdata (opentele is outdated).

Newer Desktop builds write map key types 0x17–0x1e that stock opentele rejects,
which surfaces as: "No account has been loaded".
"""

from __future__ import annotations

_APPLIED = False


def apply() -> None:
    """Monkey-patch opentele MapData.read to accept current tdata map keys."""
    global _APPLIED
    if _APPLIED:
        return

    from opentele.td.account import MapData
    from opentele.td.configs import FileKey, PeerId, lskType
    from opentele.exception import (
        ExpectStreamStatus,
        Expects,
        OpenTeleException,
        TDataReadMapDataFailed,
        TDataReadMapDataIncorrectPasscode,
    )
    from opentele.td import shared as td
    from PyQt5.QtCore import QByteArray

    # Extends stock lskType (opentele stops at 0x16 / lskMasksKeys).
    LSK_CUSTOM_EMOJI_KEYS = 0x17
    LSK_SEARCH_SUGGESTIONS = 0x18
    LSK_WEBVIEW_TOKENS = 0x19
    LSK_ROUND_PLACEHOLDER = 0x1A
    LSK_INLINE_BOTS_DOWNLOADS = 0x1B
    LSK_MEDIA_LAST_PLAYBACK = 0x1C
    LSK_BOT_STORAGES = 0x1D
    LSK_PREFS = 0x1E

    def read(self, localKey: td.AuthKey, legacyPasscode: QByteArray) -> None:
        try:
            mapData = td.Storage.ReadFile("map", self.basePath)
        except OpenTeleException as e:
            raise TDataReadMapDataFailed(
                "Could not read map data, find not found or couldn't be opened"
            ) from e

        legacySalt, legacyKeyEncrypted, mapEncrypted = (
            QByteArray(),
            QByteArray(),
            QByteArray(),
        )

        mapData.stream >> legacySalt >> legacyKeyEncrypted >> mapEncrypted
        ExpectStreamStatus(mapData.stream, "Could not stream data from mapData")

        if not localKey:
            Expects(
                legacySalt.size() == 32,
                TDataReadMapDataFailed(
                    f"Bad salt in map file, size: {legacySalt.size()}"
                ),
            )
            legacyPasscodeKey = td.Storage.CreateLegacyLocalKey(
                legacySalt, legacyPasscode
            )
            try:
                keyData = td.Storage.DecryptLocal(legacyKeyEncrypted, legacyPasscodeKey)
            except OpenTeleException as e:
                raise TDataReadMapDataIncorrectPasscode(
                    "Could not decrypt pass-protected key from map file, maybe bad password..."
                ) from e
            localKey = td.AuthKey.FromStream(keyData.stream)

        try:
            map_desc = td.Storage.DecryptLocal(mapEncrypted, localKey)
        except OpenTeleException as e:
            raise TDataReadMapDataFailed("Could not decrypt map data") from e

        selfSerialized = QByteArray()
        draftsMap = {}
        draftCursorsMap = {}
        draftsNotReadMap = {}

        locationsKey = 0
        trustedBotsKey = 0
        recentStickersKeyOld = 0
        installedStickersKey = 0
        featuredStickersKey = 0
        recentStickersKey = 0
        favedStickersKey = 0
        archivedStickersKey = 0
        installedMasksKey = 0
        recentMasksKey = 0
        archivedMasksKey = 0
        savedGifsKey = 0
        legacyBackgroundKeyDay = 0
        legacyBackgroundKeyNight = 0
        userSettingsKey = 0
        recentHashtagsAndBotsKey = 0
        exportSettingsKey = 0

        while not map_desc.stream.atEnd():
            keyType = map_desc.stream.readUInt32()

            if keyType == lskType.lskDraft:
                count = map_desc.stream.readUInt32()
                for _ in range(count):
                    key = FileKey(map_desc.stream.readUInt64())
                    peerIdSerialized = map_desc.stream.readUInt64()
                    peerId = PeerId.FromSerialized(peerIdSerialized)
                    draftsMap[peerId] = key
                    draftsNotReadMap[peerId] = True

            elif keyType == lskType.lskSelfSerialized:
                map_desc.stream >> selfSerialized

            elif keyType == lskType.lskDraftPosition:
                count = map_desc.stream.readUInt32()
                for _ in range(count):
                    key = FileKey(map_desc.stream.readUInt64())
                    peerIdSerialized = map_desc.stream.readUInt64()
                    peerId = PeerId.FromSerialized(peerIdSerialized)
                    draftCursorsMap[peerId] = key

            elif keyType in (
                lskType.lskLegacyImages,
                lskType.lskLegacyStickerImages,
                lskType.lskLegacyAudios,
            ):
                count = map_desc.stream.readUInt32()
                for _ in range(count):
                    map_desc.stream.readUInt64()
                    map_desc.stream.readUInt64()
                    map_desc.stream.readUInt64()
                    map_desc.stream.readInt32()

            elif keyType == lskType.lskLocations:
                locationsKey = map_desc.stream.readUInt64()

            elif keyType == lskType.lskReportSpamStatusesOld:
                map_desc.stream.readUInt64()

            elif keyType == lskType.lskTrustedBots:
                trustedBotsKey = map_desc.stream.readUInt64()

            elif keyType == lskType.lskRecentStickersOld:
                recentStickersKeyOld = map_desc.stream.readUInt64()

            elif keyType == lskType.lskBackgroundOldOld:
                map_desc.stream >> legacyBackgroundKeyDay

            elif keyType == lskType.lskBackgroundOld:
                legacyBackgroundKeyDay = map_desc.stream.readUInt64()
                legacyBackgroundKeyNight = map_desc.stream.readUInt64()

            elif keyType == lskType.lskUserSettings:
                userSettingsKey = map_desc.stream.readUInt64()

            elif keyType == lskType.lskRecentHashtagsAndBots:
                recentHashtagsAndBotsKey = map_desc.stream.readUInt64()

            elif keyType == lskType.lskStickersOld:
                installedStickersKey = map_desc.stream.readUInt64()

            elif keyType == lskType.lskStickersKeys:
                installedStickersKey = map_desc.stream.readUInt64()
                featuredStickersKey = map_desc.stream.readUInt64()
                recentStickersKey = map_desc.stream.readUInt64()
                archivedStickersKey = map_desc.stream.readUInt64()

            elif keyType == lskType.lskFavedStickers:
                favedStickersKey = map_desc.stream.readUInt64()

            elif keyType == lskType.lskSavedGifsOld:
                map_desc.stream.readUInt64()

            elif keyType == lskType.lskSavedGifs:
                savedGifsKey = map_desc.stream.readUInt64()

            elif keyType == lskType.lskSavedPeersOld:
                map_desc.stream.readUInt64()

            elif keyType == lskType.lskExportSettings:
                exportSettingsKey = map_desc.stream.readUInt64()

            elif keyType == lskType.lskMasksKeys:
                installedMasksKey = map_desc.stream.readUInt64()
                recentMasksKey = map_desc.stream.readUInt64()
                archivedMasksKey = map_desc.stream.readUInt64()

            # Modern Telegram Desktop keys (missing from stock opentele)
            elif keyType == LSK_CUSTOM_EMOJI_KEYS:
                map_desc.stream.readUInt64()
                map_desc.stream.readUInt64()
                map_desc.stream.readUInt64()

            elif keyType == LSK_SEARCH_SUGGESTIONS:
                map_desc.stream.readUInt64()

            elif keyType == LSK_WEBVIEW_TOKENS:
                bots = QByteArray()
                other = QByteArray()
                map_desc.stream >> bots >> other

            elif keyType == LSK_ROUND_PLACEHOLDER:
                map_desc.stream.readUInt64()

            elif keyType == LSK_INLINE_BOTS_DOWNLOADS:
                map_desc.stream.readUInt64()

            elif keyType == LSK_MEDIA_LAST_PLAYBACK:
                map_desc.stream.readUInt64()

            elif keyType == LSK_BOT_STORAGES:
                count = map_desc.stream.readUInt32()
                for _ in range(count):
                    map_desc.stream.readUInt64()
                    map_desc.stream.readUInt64()

            elif keyType == LSK_PREFS:
                map_desc.stream.readUInt64()

            else:
                # Best-effort for future single-FileKey entries
                try:
                    map_desc.stream.readUInt64()
                except Exception as exc:
                    raise TDataReadMapDataFailed(
                        f"Unknown key type in encrypted map: {keyType}"
                    ) from exc

            ExpectStreamStatus(map_desc.stream, "Could not stream data from mapData ")

        self.__localKey = localKey  # noqa: SLF001
        _ = selfSerialized  # kept for parity with Desktop map layout

        self._draftsMap = draftsMap
        self._draftCursorsMap = draftCursorsMap
        self._draftsNotReadMap = draftsNotReadMap

        self._locationsKey = locationsKey
        self._trustedBotsKey = trustedBotsKey
        self._recentStickersKeyOld = recentStickersKeyOld
        self._installedStickersKey = installedStickersKey
        self._featuredStickersKey = featuredStickersKey
        self._recentStickersKey = recentStickersKey
        self._favedStickersKey = favedStickersKey
        self._archivedStickersKey = archivedStickersKey
        self._savedGifsKey = savedGifsKey
        self._installedMasksKey = installedMasksKey
        self._recentMasksKey = recentMasksKey
        self._archivedMasksKey = archivedMasksKey
        self._legacyBackgroundKeyDay = legacyBackgroundKeyDay
        self._legacyBackgroundKeyNight = legacyBackgroundKeyNight
        self._settingsKey = userSettingsKey
        self._recentHashtagsAndBotsKey = recentHashtagsAndBotsKey
        self._exportSettingsKey = exportSettingsKey
        self._oldMapVersion = mapData.version

    MapData.read = read  # type: ignore[method-assign]
    _APPLIED = True
