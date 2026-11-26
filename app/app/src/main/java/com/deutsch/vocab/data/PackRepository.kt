package com.deutsch.vocab.data

import android.content.Context
import android.net.Uri
import org.json.JSONArray
import org.json.JSONObject
import java.io.BufferedInputStream
import java.io.File
import java.io.FileOutputStream
import java.util.zip.ZipInputStream

class PackRepository(private val context: Context) {

    private val packsRoot: File
        get() = File(context.filesDir, "packs").also { it.mkdirs() }

    private val progressRoot: File
        get() = File(context.filesDir, "progress").also { it.mkdirs() }

    fun listDeckInfos(): List<DeckInfo> {
        val levels = listOf("A1", "A2", "B1", "B2")
        return levels.map { level ->
            val dir = File(packsRoot, level)
            if (!dir.exists()) {
                DeckInfo(level, level, false, 0, 0, 0, 0, 0, 1)
            } else {
                val words = loadWords(level)
                val progress = loadAllProgress(level)
                val counts = countStatuses(words, progress)
                val manifest = loadManifest(level)
                DeckInfo(
                    level = level,
                    title = manifest?.title ?: level,
                    installed = true,
                    wordCount = words.size,
                    easy = counts.easy,
                    unseen = counts.unseen,
                    unknown = counts.unknown,
                    learning = counts.learning,
                    round = currentRound(words, progress)
                )
            }
        }
    }

    fun importPack(uri: Uri): Result<PackManifest> = runCatching {
        context.contentResolver.openInputStream(uri)?.use { input ->
            val tmp = File(context.cacheDir, "import_tmp.deword")
            FileOutputStream(tmp).use { out -> input.copyTo(out) }
            importPackFile(tmp)
        } ?: error("无法打开文件")
    }

    fun importPackFile(file: File): PackManifest {
        val staging = File(context.cacheDir, "pack_staging").also {
            if (it.exists()) it.deleteRecursively()
            it.mkdirs()
        }
        ZipInputStream(BufferedInputStream(file.inputStream())).use { zis ->
            var entry = zis.nextEntry
            while (entry != null) {
                val outFile = File(staging, entry.name)
                if (entry.isDirectory) {
                    outFile.mkdirs()
                } else {
                    outFile.parentFile?.mkdirs()
                    FileOutputStream(outFile).use { zis.copyTo(it) }
                }
                zis.closeEntry()
                entry = zis.nextEntry
            }
        }
        val manifestFile = File(staging, "manifest.json")
        require(manifestFile.exists()) { "缺少 manifest.json" }
        val wordsFile = File(staging, "words.json")
        require(wordsFile.exists()) { "缺少 words.json" }
        val manifest = parseManifest(JSONObject(manifestFile.readText(Charsets.UTF_8)))
        require(manifest.format == "deword") { "不是有效的 deword 词库包" }
        require(manifest.level in setOf("A1", "A2", "B1", "B2")) { "不支持的等级: ${manifest.level}" }

        val target = File(packsRoot, manifest.level)
        if (target.exists()) target.deleteRecursively()
        staging.copyRecursively(target, overwrite = true)
        staging.deleteRecursively()

        // Ensure progress entries exist for new words
        val words = loadWords(manifest.level)
        val progress = loadAllProgress(manifest.level).toMutableMap()
        words.forEach { w ->
            if (w.id !in progress) {
                progress[w.id] = WordProgress(w.id)
            }
        }
        saveAllProgress(manifest.level, progress)
        return manifest
    }

    fun deletePack(level: String) {
        File(packsRoot, level).deleteRecursively()
        File(progressRoot, "$level.json").delete()
    }

    fun loadManifest(level: String): PackManifest? {
        val f = File(File(packsRoot, level), "manifest.json")
        if (!f.exists()) return null
        return parseManifest(JSONObject(f.readText(Charsets.UTF_8)))
    }

    fun loadWords(level: String): List<Word> {
        val f = File(File(packsRoot, level), "words.json")
        if (!f.exists()) return emptyList()
        val arr = JSONArray(f.readText(Charsets.UTF_8))
        return buildList {
            for (i in 0 until arr.length()) {
                add(parseWord(arr.getJSONObject(i)))
            }
        }.sortedBy { it.rank }
    }

    fun mediaFile(level: String, relativePath: String?): File? {
        if (relativePath.isNullOrBlank()) return null
        val f = File(File(packsRoot, level), relativePath)
        return f.takeIf { it.exists() }
    }

    fun loadAllProgress(level: String): Map<String, WordProgress> {
        val f = File(progressRoot, "$level.json")
        if (!f.exists()) return emptyMap()
        val obj = JSONObject(f.readText(Charsets.UTF_8))
        val map = mutableMapOf<String, WordProgress>()
        obj.keys().forEach { id ->
            val o = obj.getJSONObject(id)
            map[id] = WordProgress(
                wordId = id,
                status = WordStatus.fromStored(o.optString("status", WordStatus.UNSEEN.name)),
                passCount = o.optInt("pass_count"),
                wrongCount = o.optInt("wrong_count")
            )
        }
        return map
    }

    fun saveAllProgress(level: String, progress: Map<String, WordProgress>) {
        val obj = JSONObject()
        progress.values.forEach { p ->
            obj.put(
                p.wordId,
                JSONObject()
                    .put("status", p.status.name)
                    .put("pass_count", p.passCount)
                    .put("wrong_count", p.wrongCount)
            )
        }
        File(progressRoot, "$level.json").writeText(obj.toString(), Charsets.UTF_8)
    }

    fun updateProgress(level: String, wordId: String, transform: (WordProgress) -> WordProgress) {
        val all = loadAllProgress(level).toMutableMap()
        val current = all[wordId] ?: WordProgress(wordId)
        all[wordId] = transform(current)
        saveAllProgress(level, all)
    }

    fun wordsWithStatus(level: String, status: WordStatus): List<Word> {
        val progress = loadAllProgress(level)
        return loadWords(level).filter { w ->
            (progress[w.id]?.status ?: WordStatus.UNSEEN) == status
        }
    }

    fun wordById(level: String, wordId: String): Word? =
        loadWords(level).firstOrNull { it.id == wordId }

    data class SearchHit(val level: String, val word: Word)

    /** In-memory scan of installed packs (≈3k words ≈1ms); safe for per-keystroke filter. */
    fun searchInstalledWords(query: String, limit: Int = 80): List<SearchHit> {
        val needle = query.trim().lowercase()
        if (needle.isEmpty()) return emptyList()
        val out = ArrayList<SearchHit>(limit)
        for (level in listOf("A1", "A2", "B1", "B2")) {
            if (!File(packsRoot, level).exists()) continue
            for (w in loadWords(level)) {
                if (
                    w.lemma.lowercase().contains(needle) ||
                    w.defZh.lowercase().contains(needle) ||
                    w.defEn.lowercase().contains(needle) ||
                    w.ipa.lowercase().contains(needle)
                ) {
                    out.add(SearchHit(level, w))
                    if (out.size >= limit) return out
                }
            }
        }
        return out
    }

    /**
     * Round = 1 + min(passCount) over non-Easy words.
     * Easy words stay chopped across rounds and are excluded from the queue and round gate.
     */
    fun currentRound(words: List<Word>, progress: Map<String, WordProgress>): Int {
        val active = words.filter { w ->
            (progress[w.id]?.status ?: WordStatus.UNSEEN) != WordStatus.EASY
        }
        if (active.isEmpty()) return 1
        return active.minOf { w -> progress[w.id]?.passCount ?: 0 } + 1
    }

    /**
     * After a full drill pass: keep Easy; reset everyone else to 未看过
     * (clears 不会 / 学习中). passCount is kept so「第几轮」still advances.
     */
    fun resetNonEasyAfterRound(level: String) {
        val words = loadWords(level)
        if (words.isEmpty()) return
        val all = loadAllProgress(level).toMutableMap()
        var changed = false
        words.forEach { w ->
            val p = all[w.id] ?: WordProgress(w.id)
            if (p.status != WordStatus.EASY) {
                val next = p.copy(status = WordStatus.UNSEEN, wrongCount = 0)
                if (next != p) {
                    all[w.id] = next
                    changed = true
                }
            }
        }
        if (changed) saveAllProgress(level, all)
    }

    private data class StatusCounts(
        val easy: Int,
        val unseen: Int,
        val unknown: Int,
        val learning: Int
    )

    private fun countStatuses(
        words: List<Word>,
        progress: Map<String, WordProgress>
    ): StatusCounts {
        var easy = 0
        var unseen = 0
        var unknown = 0
        var learning = 0
        words.forEach { w ->
            when (progress[w.id]?.status ?: WordStatus.UNSEEN) {
                WordStatus.EASY -> easy++
                WordStatus.UNSEEN -> unseen++
                WordStatus.UNKNOWN -> unknown++
                WordStatus.LEARNING -> learning++
            }
        }
        return StatusCounts(easy, unseen, unknown, learning)
    }
}
