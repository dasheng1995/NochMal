package com.deutsch.vocab.ui

import android.app.Application
import android.media.AudioManager
import android.media.MediaPlayer
import android.media.ToneGenerator
import android.os.Handler
import android.os.Looper
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableIntStateOf
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.setValue
import androidx.lifecycle.AndroidViewModel
import com.deutsch.vocab.R
import com.deutsch.vocab.data.PackRepository
import com.deutsch.vocab.data.Word
import com.deutsch.vocab.data.WordStatus
import java.io.File

data class QuizOption(
    val label: String,
    val wordId: String?
)

data class QuizQuestion(
    val word: Word,
    val options: List<QuizOption>,
    val correctIndex: Int,
    val imageFile: File?,
    val audioWordFile: File?,
    val audioSentenceFile: File?
)

/** Detail overlay: either the just-answered word, or a previous word opened from the top chip. */
data class DetailSession(
    val word: Word,
    val imageFile: File?,
    val audioWordFile: File?,
    val audioSentenceFile: File?,
    val isHistory: Boolean,
    val isEasy: Boolean
)

class QuizViewModel(app: Application) : AndroidViewModel(app) {
    private val repo = PackRepository(app)
    private var player: MediaPlayer? = null
    private var sfxPlayer: MediaPlayer? = null
    private val mainHandler = Handler(Looper.getMainLooper())

    var level by mutableStateOf("A1")
        private set
    var queue by mutableStateOf<List<Word>>(emptyList())
        private set
    var index by mutableIntStateOf(0)
        private set
    var question by mutableStateOf<QuizQuestion?>(null)
        private set
    var wrongIndices by mutableStateOf<Set<Int>>(emptySet())
        private set
    var showDetail by mutableStateOf(false)
        private set
    var finished by mutableStateOf(false)
        private set
    var previousSummary by mutableStateOf("")
        private set
    var previousWord by mutableStateOf<Word?>(null)
        private set
    var detailSession by mutableStateOf<DetailSession?>(null)
        private set
    /** Bumps when detail opens so UI can auto-play sentence. */
    var detailOpenToken by mutableIntStateOf(0)
        private set

    /**
     * Deck total progress: (total - unseen) / total.
     * Denominator = full deck size including 斩. 斩 is never 未看过, so it always
     * counts as already done (as if seen every round).
     */
    val progressFraction: Float
        get() {
            val words = repo.loadWords(level)
            val total = words.size
            if (total == 0) return 0f
            val progress = repo.loadAllProgress(level)
            // 未看过 only; Easy / Learning / Unknown all count toward done.
            val unseen = words.count { w ->
                (progress[w.id]?.status ?: WordStatus.UNSEEN) == WordStatus.UNSEEN
            }
            return ((total - unseen).toFloat() / total.toFloat()).coerceIn(0f, 1f)
        }

    fun start(level: String) {
        this.level = level
        val words = repo.loadWords(level)
        val progress = repo.loadAllProgress(level)
        // Same round: only queue words not yet passed this round (passCount < currentRound).
        // Restarting mid-round must not re-include 学习中 / 不会 that already got a pass.
        val round = repo.currentRound(words, progress)
        queue = words.filter { w ->
            val p = progress[w.id]
            (p?.status ?: WordStatus.UNSEEN) != WordStatus.EASY &&
                (p?.passCount ?: 0) < round
        }.shuffled()
        index = 0
        finished = false
        previousSummary = ""
        previousWord = null
        detailSession = null
        showDetail = false
        loadCurrent()
    }

    fun loadCurrent() {
        wrongIndices = emptySet()
        showDetail = false
        detailSession = null
        if (index >= queue.size) {
            // Full queue done = one round finished; keep 斩, reset other buckets.
            repo.resetNonEasyAfterRound(level)
            finished = true
            question = null
            return
        }
        val word = queue[index]
        val distractors = queue
            .filter { it.id != word.id }
            .shuffled()
            .take(3)
            .map { QuizOption(it.optionLabel, it.id) }
            .toMutableList()
        while (distractors.size < 3) {
            distractors.add(QuizOption("（干扰项）\n(distractor)", null))
        }
        val options = (distractors + QuizOption(word.optionLabel, word.id)).shuffled()
        val correctIndex = options.indexOfFirst { it.wordId == word.id }.coerceAtLeast(0)
        question = QuizQuestion(
            word = word,
            options = options,
            correctIndex = correctIndex,
            imageFile = repo.mediaFile(level, word.image.path),
            audioWordFile = repo.mediaFile(level, word.audioWord),
            audioSentenceFile = repo.mediaFile(level, word.audioSentence)
        )
        playWordAudio()
    }

    fun selectOption(i: Int) {
        if (showDetail) return
        val q = question ?: return
        if (i in wrongIndices) return
        if (i == q.correctIndex) {
            playAnswerSfx(correct = true)
            // Once wrong (≥1), stay in 不会 even after a later correct answer.
            val wrongThisTurn = wrongIndices.isNotEmpty()
            repo.updateProgress(level, q.word.id) { p ->
                val keepUnknown =
                    wrongThisTurn || p.wrongCount > 0 || p.status == WordStatus.UNKNOWN
                p.copy(
                    status = if (keepUnknown) WordStatus.UNKNOWN else WordStatus.LEARNING,
                    passCount = p.passCount + 1
                )
            }
            openDetailFor(q.word, isHistory = false)
        } else {
            playAnswerSfx(correct = false)
            wrongIndices = wrongIndices + i
            repo.updateProgress(level, q.word.id) { p ->
                p.copy(status = WordStatus.UNKNOWN, wrongCount = p.wrongCount + 1)
            }
        }
    }

    /** Correct: Mixkit sci-fi click (raw); wrong: short system NACK. */
    private fun playAnswerSfx(correct: Boolean) {
        if (correct) {
            runCatching {
                sfxPlayer?.release()
                sfxPlayer = MediaPlayer.create(getApplication(), R.raw.sfx_correct)?.also { mp ->
                    mp.setVolume(0.1f, 0.1f)
                    mp.setOnCompletionListener {
                        runCatching { it.release() }
                        if (sfxPlayer === it) sfxPlayer = null
                    }
                    mp.start()
                }
            }
            return
        }
        runCatching {
            val durationMs = 180
            val tg = ToneGenerator(AudioManager.STREAM_MUSIC, 70)
            tg.startTone(ToneGenerator.TONE_PROP_NACK, durationMs)
            mainHandler.postDelayed({ runCatching { tg.release() } }, (durationMs + 80).toLong())
        }
    }

    fun openPreviousDetail() {
        val w = previousWord ?: return
        openDetailFor(w, isHistory = true)
    }

    private fun openDetailFor(word: Word, isHistory: Boolean) {
        val progress = repo.loadAllProgress(level)[word.id]
        detailSession = DetailSession(
            word = word,
            imageFile = repo.mediaFile(level, word.image.path),
            audioWordFile = repo.mediaFile(level, word.audioWord),
            audioSentenceFile = repo.mediaFile(level, word.audioSentence),
            isHistory = isHistory,
            isEasy = progress?.status == WordStatus.EASY
        )
        showDetail = true
        detailOpenToken += 1
    }

    fun closeDetailToQuiz() {
        showDetail = false
        detailSession = null
    }

    fun markEasy() {
        val session = detailSession
        if (session != null) {
            repo.updateProgress(level, session.word.id) {
                it.copy(status = WordStatus.EASY, passCount = maxOf(it.passCount, 1))
            }
            if (session.isHistory) {
                detailSession = session.copy(isEasy = true)
                if (previousWord?.id == session.word.id) {
                    previousSummary = "${session.word.lemma}: ${session.word.detailDefLine}"
                }
                return
            }
            rememberPrevious(session.word)
            index += 1
            loadCurrent()
            return
        }
        val q = question ?: return
        repo.updateProgress(level, q.word.id) {
            it.copy(status = WordStatus.EASY, passCount = maxOf(it.passCount, 1))
        }
        rememberPrevious(q.word)
        index += 1
        loadCurrent()
    }

    fun unmarkEasy() {
        val session = detailSession ?: return
        repo.updateProgress(level, session.word.id) {
            it.copy(status = WordStatus.LEARNING)
        }
        detailSession = session.copy(isEasy = false)
    }

    fun nextFromDetail() {
        val session = detailSession
        if (session?.isHistory == true) {
            // Return to the current quiz word (adjacent next relative to the reviewed one).
            closeDetailToQuiz()
            return
        }
        val q = question ?: return
        rememberPrevious(q.word)
        index += 1
        loadCurrent()
    }

    private fun rememberPrevious(word: Word) {
        previousWord = word
        previousSummary = "${word.lemma}: ${word.detailDefLine}"
    }

    fun playWordAudio() = playFile(detailSession?.audioWordFile ?: question?.audioWordFile)

    fun playSentenceAudio() = playFile(
        detailSession?.audioSentenceFile
            ?: detailSession?.audioWordFile
            ?: question?.audioSentenceFile
            ?: question?.audioWordFile
    )

    private fun playFile(file: File?) {
        if (file == null) return
        runCatching {
            player?.release()
            player = MediaPlayer().apply {
                setDataSource(file.absolutePath)
                prepare()
                start()
            }
        }
    }

    override fun onCleared() {
        mainHandler.removeCallbacksAndMessages(null)
        player?.release()
        sfxPlayer?.release()
        super.onCleared()
    }
}
