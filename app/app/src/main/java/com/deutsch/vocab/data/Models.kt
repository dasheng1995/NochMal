package com.deutsch.vocab.data

import org.json.JSONObject

data class WordImage(
    val path: String,
    val source: String = "",
    val queryOrPrompt: String = ""
)

data class Word(
    val id: String,
    val rank: Int,
    val lemma: String,
    val ipa: String,
    val level: String,
    val pos: String,
    val defEn: String,
    val defZh: String,
    /** Full Chinese senses from Dehelper (detail). Falls back to defZh when blank. */
    val defZhFull: String = "",
    val exampleDe: String,
    val exampleEn: String,
    val exampleZh: String,
    val audioWord: String?,
    val audioSentence: String?,
    val image: WordImage
) {
    private fun looksChinese(s: String): Boolean =
        s.any { it.code in 0x4E00..0x9FFF }

    private fun splitSenses(zh: String): List<String> =
        zh.split('；', ';')
            .map { it.trim() }
            .filter { it.isNotBlank() }

    /** Quiz Chinese: at most 2 senses. */
    private val zhLine: String
        get() {
            val zh = defZh.trim()
            val raw = when {
                looksChinese(zh) -> zh
                looksChinese(defEn.trim()) -> defEn.trim()
                else -> zh.ifBlank { defEn.trim() }
            }
            if (!looksChinese(raw)) return raw
            return splitSenses(raw).take(2).joinToString("；").ifBlank { raw }
        }

    private val enLine: String
        get() {
            val en = defEn.trim()
            return if (looksChinese(en)) "" else en
        }

    /** Detail Chinese: all Dehelper senses when present. */
    private val zhDetailLine: String
        get() {
            val full = defZhFull.trim()
            val zh = defZh.trim()
            return when {
                looksChinese(full) -> full
                looksChinese(zh) -> zh
                else -> zhLine
            }
        }

    /** Quiz options: hide der/die/das so gender does not leak the answer. */
    private val quizPosTag: String
        get() = when (pos.trim().lowercase()) {
            "der", "die", "das", "n", "noun", "subst" -> "N"
            else -> pos.trim()
        }

    /** Each option: Chinese (≤2 senses) + English on two lines. */
    val optionLabel: String
        get() {
            val zh = zhLine
            val en = enLine
            val body = when {
                zh.isNotBlank() && en.isNotBlank() && zh != en -> "$zh\n$en"
                zh.isNotBlank() -> zh
                else -> en
            }
            val tag = quizPosTag
            return if (tag.isBlank()) body else "$tag. $body"
        }

    /** Detail page: POS + Chinese (full Dehelper) + English gloss. */
    val detailDefLine: String
        get() {
            val zh = zhDetailLine
            val en = enLine
            val body = when {
                zh.isNotBlank() && en.isNotBlank() && zh != en -> "$zh；$en"
                zh.isNotBlank() -> zh
                else -> en
            }
            val tag = pos.trim()
            return when {
                tag.isBlank() -> body
                body.isBlank() -> tag
                else -> "$tag. $body"
            }
        }

    val exampleZhDisplay: String
        get() {
            val zh = exampleZh.trim()
            val en = exampleEn.trim()
            return when {
                looksChinese(zh) && zh != en -> zh
                else -> ""
            }
        }
}

data class PackManifest(
    val format: String,
    val version: Int,
    val level: String,
    val packId: String,
    val title: String,
    val wordCount: Int,
    val contentHash: String,
    val notes: String = ""
)

enum class WordStatus {
    EASY, UNSEEN, UNKNOWN, LEARNING;

    companion object {
        fun fromStored(raw: String): WordStatus = when (raw) {
            "FUZZY" -> LEARNING // legacy: fuzzy removed
            else -> runCatching { valueOf(raw) }.getOrDefault(UNSEEN)
        }
    }
}

data class WordProgress(
    val wordId: String,
    val status: WordStatus = WordStatus.UNSEEN,
    val passCount: Int = 0,
    val wrongCount: Int = 0
)

data class DeckInfo(
    val level: String,
    val title: String,
    val installed: Boolean,
    val wordCount: Int,
    val easy: Int,
    val unseen: Int,
    val unknown: Int,
    val learning: Int,
    /** Current study round (1-based). +1 when every non-Easy word has been learned once. */
    val round: Int = 1
)

fun parseWord(obj: JSONObject): Word {
    val imageObj = obj.optJSONObject("image")
    return Word(
        id = obj.getString("id"),
        rank = obj.optInt("rank"),
        lemma = obj.getString("lemma"),
        ipa = obj.optString("ipa"),
        level = obj.optString("level"),
        pos = obj.optString("pos"),
        defEn = obj.optString("def_en"),
        defZh = obj.optString("def_zh"),
        defZhFull = obj.optString("def_zh_full"),
        exampleDe = obj.optString("example_de"),
        exampleEn = obj.optString("example_en"),
        exampleZh = obj.optString("example_zh"),
        audioWord = obj.optString("audio_word").ifBlank { null },
        audioSentence = obj.optString("audio_sentence").ifBlank { null },
        image = WordImage(
            path = imageObj?.optString("path").orEmpty(),
            source = imageObj?.optString("source").orEmpty(),
            queryOrPrompt = imageObj?.optString("query_or_prompt").orEmpty()
        )
    )
}

fun parseManifest(obj: JSONObject): PackManifest = PackManifest(
    format = obj.optString("format"),
    version = obj.optInt("version"),
    level = obj.getString("level"),
    packId = obj.optString("pack_id"),
    title = obj.optString("title"),
    wordCount = obj.optInt("word_count"),
    contentHash = obj.optString("content_hash"),
    notes = obj.optString("notes")
)
