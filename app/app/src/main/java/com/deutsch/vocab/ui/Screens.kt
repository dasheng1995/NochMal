package com.deutsch.vocab.ui

import androidx.activity.compose.rememberLauncherForActivityResult
import androidx.activity.result.contract.ActivityResultContracts
import androidx.compose.animation.AnimatedContent
import androidx.compose.animation.EnterTransition
import androidx.compose.animation.ExitTransition
import androidx.compose.animation.fadeIn
import androidx.compose.animation.fadeOut
import androidx.compose.animation.slideInHorizontally
import androidx.compose.animation.slideOutHorizontally
import androidx.compose.animation.togetherWith
import android.media.MediaPlayer
import androidx.activity.compose.BackHandler
import androidx.compose.foundation.background
import androidx.compose.foundation.border
import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.BoxWithConstraints
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxHeight
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.heightIn
import androidx.compose.foundation.layout.navigationBarsPadding
import androidx.compose.foundation.layout.offset
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.foundation.text.selection.SelectionContainer
import androidx.compose.foundation.verticalScroll
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.automirrored.filled.ArrowBack
import androidx.compose.material.icons.automirrored.filled.KeyboardArrowRight
import androidx.compose.material.icons.automirrored.filled.VolumeUp
import androidx.compose.material.icons.filled.Bolt
import androidx.compose.material.icons.filled.UploadFile
import androidx.compose.material3.AlertDialog
import androidx.compose.material3.Button
import androidx.compose.material3.ButtonDefaults
import androidx.compose.material3.Card
import androidx.compose.material3.CardDefaults
import androidx.compose.material3.ExperimentalMaterial3Api
import androidx.compose.material3.Icon
import androidx.compose.material3.IconButton
import androidx.compose.material3.LinearProgressIndicator
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.Scaffold
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.material3.TopAppBar
import androidx.compose.material3.TopAppBarDefaults
import androidx.compose.runtime.Composable
import androidx.compose.runtime.DisposableEffect
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableIntStateOf
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.rememberCoroutineScope
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.geometry.Offset
import androidx.compose.ui.geometry.Size
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.graphics.Outline
import androidx.compose.ui.graphics.Path
import androidx.compose.ui.graphics.Shape
import androidx.compose.ui.graphics.vector.ImageVector
import androidx.compose.ui.layout.ContentScale
import androidx.compose.ui.platform.LocalDensity
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.style.TextAlign
import androidx.compose.ui.text.style.TextOverflow
import androidx.compose.ui.unit.Density
import androidx.compose.ui.unit.Dp
import androidx.compose.ui.unit.LayoutDirection
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import kotlin.math.hypot
import kotlin.math.min
import coil.compose.AsyncImage
import com.deutsch.vocab.data.DeckInfo
import com.deutsch.vocab.data.PackRepository
import com.deutsch.vocab.data.Word
import com.deutsch.vocab.data.WordStatus
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.launch
import kotlinx.coroutines.withContext
import java.io.File

private sealed interface DeckBrowse {
    data object Stats : DeckBrowse
    data class WordList(val status: WordStatus) : DeckBrowse
    data class WordDetail(val status: WordStatus, val wordId: String) : DeckBrowse
}

private fun WordStatus.label(): String = when (this) {
    WordStatus.EASY -> "Easy（斩）"
    WordStatus.UNSEEN -> "未看过"
    WordStatus.UNKNOWN -> "不会"
    WordStatus.LEARNING -> "学习中"
}

private val Bg = Color(0xFFEAF3FB)
private val CardBlue = Color(0xFFD7EAF8)
private val WrongRed = Color(0xFFF8D6D6)
private val Accent = Color(0xFF5B8DEF)

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun DeckListScreen(
    repo: PackRepository,
    onOpenDeck: (String) -> Unit,
    onImported: () -> Unit
) {
    var decks by remember { mutableStateOf(repo.listDeckInfos()) }
    var message by remember { mutableStateOf<String?>(null) }
    var homeQuery by remember { mutableStateOf("") }
    var peek by remember { mutableStateOf<PackRepository.SearchHit?>(null) }
    val scope = rememberCoroutineScope()
    val searchHits = remember(homeQuery, decks) {
        repo.searchInstalledWords(homeQuery)
    }

    val picker = rememberLauncherForActivityResult(
        ActivityResultContracts.OpenDocument()
    ) { uri ->
        if (uri == null) return@rememberLauncherForActivityResult
        scope.launch {
            val result = withContext(Dispatchers.IO) { repo.importPack(uri) }
            result.onSuccess {
                decks = repo.listDeckInfos()
                message = "已导入 ${it.title}（${it.wordCount} 词）"
                onImported()
            }.onFailure {
                message = "导入失败：${it.message}"
            }
        }
    }

    peek?.let { hit ->
        BackHandler { peek = null }
        BrowseWordDetailPane(
            repo = repo,
            level = hit.level,
            word = hit.word,
            onBack = { peek = null },
            onChanged = { decks = repo.listDeckInfos() }
        )
        return
    }

    Scaffold(
        topBar = {
            TopAppBar(
                title = { Text("德词轮刷") },
                actions = {
                    IconButton(onClick = {
                        picker.launch(arrayOf("application/zip", "application/octet-stream", "*/*"))
                    }) {
                        Icon(Icons.Default.UploadFile, contentDescription = "导入词库")
                    }
                }
            )
        },
        containerColor = Bg
    ) { padding ->
        Column(
            Modifier
                .padding(padding)
                .padding(16.dp)
                .fillMaxSize()
        ) {
            OutlinedTextField(
                value = homeQuery,
                onValueChange = { homeQuery = it },
                modifier = Modifier.fillMaxWidth(),
                singleLine = true,
                placeholder = { Text("搜索全部已安装词库…") },
                shape = RoundedCornerShape(12.dp)
            )
            Spacer(Modifier.height(8.dp))
            if (homeQuery.isNotBlank()) {
                Text(
                    "匹配 ${searchHits.size}${if (searchHits.size >= 80) "+" else ""}",
                    color = Color.Gray,
                    fontSize = 13.sp
                )
                Spacer(Modifier.height(8.dp))
                LazyColumn(
                    modifier = Modifier.weight(1f),
                    verticalArrangement = Arrangement.spacedBy(8.dp)
                ) {
                    items(searchHits, key = { "${it.level}_${it.word.id}" }) { hit ->
                        Row(
                            Modifier
                                .fillMaxWidth()
                                .clip(RoundedCornerShape(12.dp))
                                .background(Color.White)
                                .clickable { peek = hit }
                                .padding(horizontal = 14.dp, vertical = 12.dp),
                            verticalAlignment = Alignment.CenterVertically
                        ) {
                            Column(Modifier.weight(1f)) {
                                Text(
                                    hit.word.lemma,
                                    fontWeight = FontWeight.SemiBold,
                                    fontSize = 16.sp,
                                    maxLines = 2,
                                    overflow = TextOverflow.Ellipsis
                                )
                                Text(
                                    hit.word.detailDefLine,
                                    color = Color(0xFF666666),
                                    fontSize = 12.sp,
                                    maxLines = 2,
                                    overflow = TextOverflow.Ellipsis
                                )
                            }
                            Text(
                                hit.level,
                                color = Accent,
                                fontWeight = FontWeight.Bold,
                                fontSize = 13.sp
                            )
                        }
                    }
                }
            } else {
                Text("导入 .deword 词库包后开始刷词", color = Color.Gray)
                Spacer(Modifier.height(8.dp))
                Button(onClick = {
                    picker.launch(arrayOf("application/zip", "application/octet-stream", "*/*"))
                }) { Text("导入词库") }
                message?.let {
                    Spacer(Modifier.height(8.dp))
                    Text(it, color = MaterialTheme.colorScheme.primary)
                }
                Spacer(Modifier.height(16.dp))
                LazyColumn(verticalArrangement = Arrangement.spacedBy(12.dp)) {
                    items(decks) { deck ->
                        DeckCard(deck, onClick = {
                            if (deck.installed) onOpenDeck(deck.level)
                            else message = "请先导入 ${deck.level} 词库"
                        })
                    }
                }
            }
        }
    }
}

@Composable
private fun DeckCard(deck: DeckInfo, onClick: () -> Unit) {
    Card(
        onClick = onClick,
        colors = CardDefaults.cardColors(containerColor = Color.White),
        modifier = Modifier.fillMaxWidth()
    ) {
        Column(Modifier.padding(16.dp)) {
            Row(Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.SpaceBetween) {
                Text(deck.level, fontWeight = FontWeight.Bold, fontSize = 22.sp)
                Text(if (deck.installed) "已安装" else "未安装", color = Color.Gray)
            }
            if (deck.installed) {
                Text(deck.title)
                Text("共 ${deck.wordCount} 词")
                Spacer(Modifier.height(8.dp))
                Text("斩 ${deck.easy} · 未看 ${deck.unseen} · 不会 ${deck.unknown} · 在学 ${deck.learning}")
            }
        }
    }
}

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun DeckHomeScreen(
    repo: PackRepository,
    level: String,
    onBack: () -> Unit,
    onStartQuiz: () -> Unit
) {
    var refreshTick by remember { mutableIntStateOf(0) }
    var browse by remember { mutableStateOf<DeckBrowse>(DeckBrowse.Stats) }
    val deck = remember(level, refreshTick) {
        repo.listDeckInfos().first { it.level == level }
    }

    fun goBackOneLevel() {
        browse = when (val b = browse) {
            is DeckBrowse.WordDetail -> DeckBrowse.WordList(b.status)
            is DeckBrowse.WordList -> DeckBrowse.Stats
            DeckBrowse.Stats -> {
                onBack()
                DeckBrowse.Stats
            }
        }
    }

    BackHandler { goBackOneLevel() }

    when (val page = browse) {
        DeckBrowse.Stats -> DeckStatsPane(
            deck = deck,
            onBack = onBack,
            onOpenStatus = { browse = DeckBrowse.WordList(it) },
            onStartQuiz = onStartQuiz,
            onDelete = {
                repo.deletePack(level)
                onBack()
            }
        )

        is DeckBrowse.WordList -> {
            val words = remember(level, page.status, refreshTick) {
                repo.wordsWithStatus(level, page.status)
            }
            StatusWordListPane(
                status = page.status,
                words = words,
                onBack = { browse = DeckBrowse.Stats },
                onOpenWord = { browse = DeckBrowse.WordDetail(page.status, it) },
                onRemoveFromEasy = if (page.status == WordStatus.EASY) {
                    { wordId ->
                        repo.updateProgress(level, wordId) {
                            it.copy(status = WordStatus.LEARNING)
                        }
                        refreshTick++
                    }
                } else {
                    null
                }
            )
        }

        is DeckBrowse.WordDetail -> {
            val word = remember(level, page.wordId, refreshTick) {
                repo.wordById(level, page.wordId)
            }
            if (word == null) {
                LaunchedEffect(Unit) { browse = DeckBrowse.WordList(page.status) }
            } else {
                BrowseWordDetailPane(
                    repo = repo,
                    level = level,
                    word = word,
                    onBack = { browse = DeckBrowse.WordList(page.status) },
                    onChanged = { refreshTick++ }
                )
            }
        }
    }
}

@OptIn(ExperimentalMaterial3Api::class)
@Composable
private fun DeckStatsPane(
    deck: DeckInfo,
    onBack: () -> Unit,
    onOpenStatus: (WordStatus) -> Unit,
    onStartQuiz: () -> Unit,
    onDelete: () -> Unit
) {
    var confirmDelete by remember { mutableStateOf(false) }

    if (confirmDelete) {
        AlertDialog(
            onDismissRequest = { confirmDelete = false },
            title = { Text("删除本词库？") },
            text = {
                Text("将删除「${deck.level} · ${deck.title}」的词库文件与本地进度，此操作不可恢复。")
            },
            confirmButton = {
                TextButton(
                    onClick = {
                        confirmDelete = false
                        onDelete()
                    }
                ) {
                    Text("删除", color = Color.Red)
                }
            },
            dismissButton = {
                TextButton(onClick = { confirmDelete = false }) {
                    Text("取消")
                }
            }
        )
    }

    Scaffold(
        topBar = {
            TopAppBar(
                title = { Text("${deck.level} · ${deck.title}") },
                navigationIcon = {
                    IconButton(onClick = onBack) {
                        Icon(Icons.AutoMirrored.Filled.ArrowBack, contentDescription = "返回")
                    }
                }
            )
        },
        containerColor = Bg
    ) { padding ->
        Column(
            Modifier
                .padding(padding)
                .padding(16.dp)
                .fillMaxSize()
        ) {
            Row(
                Modifier.fillMaxWidth(),
                horizontalArrangement = Arrangement.SpaceBetween,
                verticalAlignment = Alignment.CenterVertically
            ) {
                Text("词库统计", fontWeight = FontWeight.Bold, fontSize = 18.sp)
                TextButton(onClick = { confirmDelete = true }) {
                    Text("删除本词库", color = Color.Red, fontSize = 13.sp)
                }
            }
            Spacer(Modifier.height(8.dp))
            StatRow("Easy（斩）", deck.easy, clickable = true) { onOpenStatus(WordStatus.EASY) }
            StatRow("未看过", deck.unseen, clickable = true) { onOpenStatus(WordStatus.UNSEEN) }
            StatRow("不会", deck.unknown, clickable = true) { onOpenStatus(WordStatus.UNKNOWN) }
            StatRow("学习中", deck.learning, clickable = true) { onOpenStatus(WordStatus.LEARNING) }
            StatRow("第几轮", deck.round, clickable = false)
            Spacer(Modifier.height(24.dp))
            Button(onClick = onStartQuiz, modifier = Modifier.fillMaxWidth()) {
                Text("开始刷词")
            }
        }
    }
}

@OptIn(ExperimentalMaterial3Api::class)
@Composable
private fun StatusWordListPane(
    status: WordStatus,
    words: List<Word>,
    onBack: () -> Unit,
    onOpenWord: (String) -> Unit,
    onRemoveFromEasy: ((String) -> Unit)? = null
) {
    var query by remember { mutableStateOf("") }
    val filtered = remember(words, query) {
        val q = query.trim()
        if (q.isEmpty()) words
        else {
            val needle = q.lowercase()
            words.filter { w ->
                w.lemma.lowercase().contains(needle) ||
                    w.defZh.lowercase().contains(needle) ||
                    w.defEn.lowercase().contains(needle) ||
                    w.ipa.lowercase().contains(needle)
            }
        }
    }

    Scaffold(
        topBar = {
            TopAppBar(
                title = {
                    Text(
                        if (query.isBlank()) "${status.label()} · ${words.size}"
                        else "${status.label()} · ${filtered.size}/${words.size}"
                    )
                },
                navigationIcon = {
                    IconButton(onClick = onBack) {
                        Icon(Icons.AutoMirrored.Filled.ArrowBack, contentDescription = "返回")
                    }
                }
            )
        },
        containerColor = Bg
    ) { padding ->
        Column(
            Modifier
                .padding(padding)
                .fillMaxSize()
        ) {
            OutlinedTextField(
                value = query,
                onValueChange = { query = it },
                modifier = Modifier
                    .fillMaxWidth()
                    .padding(horizontal = 16.dp, vertical = 8.dp),
                singleLine = true,
                placeholder = { Text("搜索当前列表…") },
                shape = RoundedCornerShape(12.dp)
            )
            when {
                words.isEmpty() -> Box(
                    Modifier.fillMaxSize(),
                    contentAlignment = Alignment.Center
                ) {
                    Text("该分类暂无单词", color = Color.Gray)
                }

                filtered.isEmpty() -> Box(
                    Modifier.fillMaxSize(),
                    contentAlignment = Alignment.Center
                ) {
                    Text("无匹配单词", color = Color.Gray)
                }

                else -> LazyColumn(
                    Modifier
                        .padding(horizontal = 16.dp, vertical = 4.dp)
                        .fillMaxSize(),
                    verticalArrangement = Arrangement.spacedBy(8.dp)
                ) {
                    items(filtered, key = { it.id }) { word ->
                        Row(
                            Modifier
                                .fillMaxWidth()
                                .clip(RoundedCornerShape(12.dp))
                                .background(Color.White)
                                .clickable { onOpenWord(word.id) }
                                .padding(horizontal = 14.dp, vertical = 12.dp),
                            verticalAlignment = Alignment.CenterVertically
                        ) {
                            Column(Modifier.weight(1f)) {
                                Text(
                                    word.lemma,
                                    fontWeight = FontWeight.SemiBold,
                                    fontSize = 17.sp,
                                    maxLines = 2,
                                    overflow = TextOverflow.Ellipsis
                                )
                                Spacer(Modifier.height(2.dp))
                                Text(
                                    word.detailDefLine,
                                    color = Color(0xFF666666),
                                    fontSize = 13.sp,
                                    maxLines = 2,
                                    overflow = TextOverflow.Ellipsis
                                )
                            }
                            if (onRemoveFromEasy != null) {
                                TextButton(
                                    onClick = { onRemoveFromEasy(word.id) },
                                    modifier = Modifier.padding(end = 4.dp)
                                ) {
                                    Text("移出", color = Accent, fontSize = 13.sp)
                                }
                            }
                            Icon(
                                Icons.AutoMirrored.Filled.KeyboardArrowRight,
                                contentDescription = null,
                                tint = Color.Gray
                            )
                        }
                    }
                }
            }
        }
    }
}

@Composable
private fun BrowseWordDetailPane(
    repo: PackRepository,
    level: String,
    word: Word,
    onBack: () -> Unit,
    onChanged: () -> Unit
) {
    val player = remember { MediaPlayer() }
    DisposableEffect(Unit) {
        onDispose {
            runCatching {
                player.stop()
                player.release()
            }
        }
    }
    fun play(file: File?) {
        if (file == null) return
        runCatching {
            player.reset()
            player.setDataSource(file.absolutePath)
            player.prepare()
            player.start()
        }
    }
    val imageFile = remember(word.id) { repo.mediaFile(level, word.image.path) }
    val audioWord = remember(word.id) { repo.mediaFile(level, word.audioWord) }
    val audioSentence = remember(word.id) { repo.mediaFile(level, word.audioSentence) }

    WordDetailScreen(
        word = word,
        imageFile = imageFile,
        autoPlayToken = 0,
        continueLabel = "返回",
        autoPlay = false,
        onPlayWord = { play(audioWord) },
        onPlaySentence = { play(audioSentence ?: audioWord) },
        onEasy = {
            repo.updateProgress(level, word.id) { it.copy(status = WordStatus.EASY) }
            onChanged()
            onBack()
        },
        onContinue = onBack,
        onBack = onBack
    )
}

@Composable
private fun StatRow(
    label: String,
    count: Int,
    clickable: Boolean = false,
    onClick: (() -> Unit)? = null
) {
    Row(
        Modifier
            .fillMaxWidth()
            .padding(vertical = 6.dp)
            .clip(RoundedCornerShape(12.dp))
            .background(Color.White)
            .then(
                if (clickable && onClick != null) Modifier.clickable(onClick = onClick)
                else Modifier
            )
            .padding(14.dp),
        horizontalArrangement = Arrangement.SpaceBetween,
        verticalAlignment = Alignment.CenterVertically
    ) {
        Text(label)
        Row(verticalAlignment = Alignment.CenterVertically) {
            Text("$count", fontWeight = FontWeight.Bold)
            if (clickable) {
                Spacer(Modifier.width(4.dp))
                Icon(
                    Icons.AutoMirrored.Filled.KeyboardArrowRight,
                    contentDescription = null,
                    tint = Color.Gray,
                    modifier = Modifier.size(18.dp)
                )
            }
        }
    }
}

@Composable
fun QuizScreen(
    vm: QuizViewModel,
    level: String,
    onBack: () -> Unit
) {
    LaunchedEffect(level) { vm.start(level) }

    BackHandler {
        when {
            vm.showDetail -> vm.closeDetailToQuiz()
            else -> onBack()
        }
    }

    // Freeze detail session in targetState so exit never flashes the next word mid-animation.
    AnimatedContent(
        targetState = vm.showDetail to vm.detailSession,
        contentKey = { (detail, session) ->
            detail to session?.word?.id to session?.isHistory
        },
        transitionSpec = {
            val enteringDetail = !initialState.first && targetState.first
            val leavingDetail = initialState.first && !targetState.first
            when {
                enteringDetail || leavingDetail -> {
                    (fadeIn(FastTween) + slideInHorizontally(FastOffsetTween) { it / 6 }) togetherWith
                        (fadeOut(FastTween) + slideOutHorizontally(FastOffsetTween) { -it / 8 })
                }
                else -> EnterTransition.None togetherWith ExitTransition.None
            }
        },
        label = "quizDetail"
    ) { (detail, session) ->
        if (detail && session != null) {
            WordDetailScreen(
                word = session.word,
                imageFile = session.imageFile,
                autoPlayToken = vm.detailOpenToken,
                onPlayWord = { vm.playWordAudio() },
                onPlaySentence = { vm.playSentenceAudio() },
                onEasy = { vm.markEasy() },
                onUnchop = { vm.unmarkEasy() },
                isEasy = session.isEasy,
                onContinue = { vm.nextFromDetail() },
                onBack = { vm.closeDetailToQuiz() }
            )
        } else {
            QuizQuestionPane(vm = vm, level = level, onBack = onBack)
        }
    }
}

@OptIn(ExperimentalMaterial3Api::class)
@Composable
private fun QuizQuestionPane(
    vm: QuizViewModel,
    level: String,
    onBack: () -> Unit
) {
    val q = vm.question
    Scaffold(
        topBar = {
            TopAppBar(
                title = {
                    val summary = vm.previousSummary
                    if (summary.isNotBlank() && vm.previousWord != null) {
                        Text(
                            summary,
                            fontSize = 14.sp,
                            maxLines = 1,
                            overflow = TextOverflow.Ellipsis,
                            color = Accent,
                            modifier = Modifier.clickable { vm.openPreviousDetail() }
                        )
                    } else {
                        Text(
                            "刷词 · $level",
                            fontSize = 14.sp,
                            maxLines = 1,
                            overflow = TextOverflow.Ellipsis
                        )
                    }
                },
                navigationIcon = {
                    IconButton(onClick = onBack) {
                        Icon(Icons.AutoMirrored.Filled.ArrowBack, contentDescription = "返回")
                    }
                },
                colors = TopAppBarDefaults.topAppBarColors(containerColor = Bg)
            )
        },
        containerColor = Bg,
        bottomBar = {
            Row(
                Modifier
                    .fillMaxWidth()
                    .background(Bg)
                    .navigationBarsPadding()
                    .padding(horizontal = 8.dp, vertical = 6.dp),
                horizontalArrangement = Arrangement.SpaceEvenly,
                verticalAlignment = Alignment.CenterVertically
            ) {
                BottomAction(Icons.Default.Bolt, "斩") { vm.markEasy() }
                BottomAction(Icons.AutoMirrored.Filled.VolumeUp, "例句") { vm.playSentenceAudio() }
            }
        }
    ) { padding ->
        when {
            vm.finished -> Column(
                Modifier.padding(padding).fillMaxSize(),
                verticalArrangement = Arrangement.Center,
                horizontalAlignment = Alignment.CenterHorizontally
            ) {
                Text("本轮刷完了", fontSize = 22.sp, fontWeight = FontWeight.Bold)
                Spacer(Modifier.height(8.dp))
                Text(
                    "已斩词保留；其余已重置为未看过",
                    color = Color.Gray,
                    fontSize = 14.sp,
                    textAlign = TextAlign.Center
                )
                Spacer(Modifier.height(12.dp))
                Button(onClick = onBack) { Text("返回词库") }
            }

            q == null -> Box(
                Modifier.padding(padding).fillMaxSize(),
                contentAlignment = Alignment.Center
            ) { Text("加载中…") }

            else -> {
                val layout = remember(q.word.lemma) { quizLayoutForLemma(q.word.lemma) }
                Column(
                    Modifier
                        .padding(padding)
                        .padding(horizontal = 12.dp)
                        .fillMaxSize()
                ) {
                    LinearProgressIndicator(
                        progress = { vm.progressFraction },
                        modifier = Modifier
                            .fillMaxWidth()
                            .height(6.dp)
                            .clip(RoundedCornerShape(6.dp)),
                        color = Accent
                    )
                    Spacer(Modifier.height(4.dp))
                    AsyncImage(
                        model = q.imageFile,
                        contentDescription = "词义配图",
                        contentScale = ContentScale.Crop,
                        modifier = Modifier
                            .fillMaxWidth()
                            .weight(layout.imageWeight)
                            .clip(RoundedCornerShape(14.dp))
                            .background(Color.White)
                    )
                    Spacer(Modifier.height(4.dp))
                    SelectionContainer {
                        Text(
                            q.word.lemma,
                            fontSize = layout.lemmaSp.sp,
                            fontWeight = FontWeight.Bold,
                            lineHeight = (layout.lemmaSp + 4).sp,
                            modifier = Modifier.fillMaxWidth(),
                            textAlign = TextAlign.Center,
                            maxLines = layout.lemmaMaxLines,
                            softWrap = true,
                            overflow = TextOverflow.Ellipsis
                        )
                    }
                    Row(
                        Modifier.fillMaxWidth(),
                        horizontalArrangement = Arrangement.Center,
                        verticalAlignment = Alignment.CenterVertically
                    ) {
                        IconButton(
                            onClick = { vm.playWordAudio() },
                            modifier = Modifier.size(layout.ipaIconDp.dp)
                        ) {
                            Icon(Icons.AutoMirrored.Filled.VolumeUp, contentDescription = "单词发音")
                        }
                        Text(
                            "/${q.word.ipa}/",
                            color = Color.Gray,
                            fontSize = layout.metaSp.sp,
                            maxLines = 1,
                            overflow = TextOverflow.Ellipsis
                        )
                    }
                    // Quiz: German example only (ZH/EN after correct → detail). Wrap fully, no clip.
                    if (q.word.exampleDe.isNotBlank()) {
                        SelectionContainer {
                            Text(
                                q.word.exampleDe,
                                modifier = Modifier.fillMaxWidth(),
                                textAlign = TextAlign.Center,
                                color = Color.DarkGray,
                                fontSize = layout.exampleSp.sp,
                                lineHeight = (layout.exampleSp + 4).sp,
                                softWrap = true
                            )
                        }
                    }
                    Spacer(Modifier.height(4.dp))
                    OptionGridCompact(
                        options = q.options.map { it.label },
                        wrongIndices = vm.wrongIndices,
                        onSelect = { vm.selectOption(it) },
                        optionTextSp = layout.optionSp,
                        modifier = Modifier
                            .weight(layout.optionsWeight)
                            .fillMaxWidth()
                    )
                }
            }
        }
    }
}

/** Round every corner of a polygon (quadratic fillets). */
private fun roundedPolygonPath(points: List<Offset>, cornerR: Float): Path {
    val path = Path()
    if (points.size < 3) return path
    val n = points.size
    fun Offset.len() = hypot(x, y)
    fun Offset.norm(): Offset {
        val l = len().coerceAtLeast(0.0001f)
        return Offset(x / l, y / l)
    }
    for (i in 0 until n) {
        val prev = points[(i - 1 + n) % n]
        val curr = points[i]
        val next = points[(i + 1) % n]
        val toPrev = (prev - curr).norm()
        val toNext = (next - curr).norm()
        val maxR = min(
            (prev - curr).len() / 2f,
            (next - curr).len() / 2f
        )
        val r = min(cornerR, maxR)
        val p1 = Offset(curr.x + toPrev.x * r, curr.y + toPrev.y * r)
        val p2 = Offset(curr.x + toNext.x * r, curr.y + toNext.y * r)
        if (i == 0) path.moveTo(p1.x, p1.y) else path.lineTo(p1.x, p1.y)
        path.quadraticBezierTo(curr.x, curr.y, p2.x, p2.y)
    }
    path.close()
    return path
}

/**
 * 斩：左直边 + 右斜边（/，顶宽底窄），四角圆角。
 * 顶点：TL(0,0) TR(w,0) BR(w-skew,h) BL(0,h)
 */
private class DiagonalCutLeftShape(private val skewPx: Float) : Shape {
    override fun createOutline(
        size: Size,
        layoutDirection: LayoutDirection,
        density: Density
    ): Outline {
        val r = min(size.height / 2f, with(density) { 16.dp.toPx() })
        val skew = skewPx.coerceIn(0f, size.width * 0.45f)
        val pts = listOf(
            Offset(0f, 0f),
            Offset(size.width, 0f),
            Offset(size.width - skew, size.height),
            Offset(0f, size.height)
        )
        return Outline.Generic(roundedPolygonPath(pts, r))
    }
}

/**
 * 继续：左斜边与斩右边平行（/），右直边，四角圆角。
 * 顶点：TL(skew,0) TR(w,0) BR(w,h) BL(0,h)
 */
private class DiagonalCutRightShape(private val skewPx: Float) : Shape {
    override fun createOutline(
        size: Size,
        layoutDirection: LayoutDirection,
        density: Density
    ): Outline {
        val r = min(size.height / 2f, with(density) { 16.dp.toPx() })
        val skew = skewPx.coerceIn(0f, size.width * 0.35f)
        val pts = listOf(
            Offset(skew, 0f),
            Offset(size.width, 0f),
            Offset(size.width, size.height),
            Offset(0f, size.height)
        )
        return Outline.Generic(roundedPolygonPath(pts, r))
    }
}

@Composable
private fun BottomAction(icon: ImageVector, label: String, onClick: () -> Unit) {
    Column(
        horizontalAlignment = Alignment.CenterHorizontally,
        modifier = Modifier
            .width(72.dp)
            .pressableScale(onClick = onClick)
            .padding(vertical = 4.dp)
    ) {
        Icon(icon, contentDescription = label, modifier = Modifier.size(22.dp), tint = Color(0xFF333333))
        Spacer(Modifier.height(2.dp))
        Text(label, fontSize = 12.sp, color = Color(0xFF333333))
    }
}

/**
 * Left small 斩 + right wide 继续; parallel / cuts.
 * [gap] is the *visible* seam width. Boxes overlap by skew so the diagonal
 * insets don't add extra empty space (Row spacing alone looked like gap+skew).
 */
@Composable
private fun DetailDiagonalActionBar(
    isEasy: Boolean,
    onEasy: () -> Unit,
    onUnchop: (() -> Unit)?,
    continueLabel: String,
    onContinue: () -> Unit,
    skew: Dp = 18.dp,
    gap: Dp = 10.dp,
    barHeight: Dp = 52.dp
) {
    val density = LocalDensity.current
    val skewPx = with(density) { skew.toPx() }
    val leftFrac = if (isEasy) 0.34f else 0.24f
    val leftShape = remember(skewPx) { DiagonalCutLeftShape(skewPx) }
    val rightShape = remember(skewPx) { DiagonalCutRightShape(skewPx) }

    Box(
        Modifier
            .fillMaxWidth()
            .background(Color.White.copy(alpha = 0.96f))
            .navigationBarsPadding()
            .padding(horizontal = 14.dp, vertical = 10.dp)
    ) {
        BoxWithConstraints(
            Modifier
                .fillMaxWidth()
                .height(barHeight)
        ) {
            val leftW = maxWidth * leftFrac
            // Overlap by skew so the visible parallel seam ≈ [gap], not gap+skew.
            val rightOffset = leftW - skew + gap
            val rightW = (maxWidth - rightOffset).coerceAtLeast(0.dp)

            Box(
                Modifier
                    .align(Alignment.CenterStart)
                    .offset(x = rightOffset)
                    .width(rightW)
                    .fillMaxHeight()
                    .clip(rightShape)
                    .background(Accent)
                    .pressableScale(onClick = onContinue),
                contentAlignment = Alignment.Center
            ) {
                Text(
                    continueLabel,
                    color = Color.White,
                    fontWeight = FontWeight.Bold,
                    fontSize = 17.sp
                )
            }
            Box(
                Modifier
                    .align(Alignment.CenterStart)
                    .width(leftW)
                    .fillMaxHeight()
                    .clip(leftShape)
                    .background(Color(0xFF3A4A5C))
                    .pressableScale {
                        if (isEasy && onUnchop != null) onUnchop() else onEasy()
                    },
                contentAlignment = Alignment.Center
            ) {
                if (isEasy && onUnchop != null) {
                    Text(
                        "撤回斩",
                        color = Color.White,
                        fontWeight = FontWeight.SemiBold,
                        fontSize = 14.sp,
                        maxLines = 1
                    )
                } else {
                    Row(verticalAlignment = Alignment.CenterVertically) {
                        Icon(
                            Icons.Default.Bolt,
                            contentDescription = null,
                            tint = Color(0xFFFFD54F),
                            modifier = Modifier.size(18.dp)
                        )
                        Spacer(Modifier.width(2.dp))
                        Text(
                            "斩",
                            color = Color.White,
                            fontWeight = FontWeight.Bold,
                            fontSize = 16.sp
                        )
                    }
                }
            }
        }
    }
}

private data class QuizLayoutMetrics(
    val lemmaSp: Int,
    val lemmaMaxLines: Int,
    val metaSp: Int,
    val exampleSp: Int,
    val exampleMaxLines: Int,
    val optionSp: Int,
    val ipaIconDp: Int,
    val imageWeight: Float,
    val optionsWeight: Float
)

private data class DetailLemmaStyle(val fontSp: Int, val lineSp: Int)

/** Longer conjugations need smaller type + explicit lineHeight to avoid overlap. */
private fun detailLemmaStyle(lemma: String): DetailLemmaStyle {
    val len = lemma.length
    return when {
        len <= 18 -> DetailLemmaStyle(fontSp = 32, lineSp = 40)
        len <= 32 -> DetailLemmaStyle(fontSp = 26, lineSp = 34)
        len <= 48 -> DetailLemmaStyle(fontSp = 22, lineSp = 30)
        else -> DetailLemmaStyle(fontSp = 18, lineSp = 26)
    }
}

/** Shrink image / fonts when lemma is long so wrapped text still fits first screen. */
private fun quizLayoutForLemma(lemma: String): QuizLayoutMetrics {
    val len = lemma.length
    return when {
        len <= 18 -> QuizLayoutMetrics(
            lemmaSp = 26, lemmaMaxLines = 2, metaSp = 12,
            exampleSp = 12, exampleMaxLines = 4, optionSp = 12,
            ipaIconDp = 34, imageWeight = 0.28f, optionsWeight = 0.40f
        )
        len <= 32 -> QuizLayoutMetrics(
            lemmaSp = 22, lemmaMaxLines = 2, metaSp = 11,
            exampleSp = 11, exampleMaxLines = 4, optionSp = 11,
            ipaIconDp = 32, imageWeight = 0.24f, optionsWeight = 0.42f
        )
        len <= 48 -> QuizLayoutMetrics(
            lemmaSp = 18, lemmaMaxLines = 3, metaSp = 11,
            exampleSp = 10, exampleMaxLines = 4, optionSp = 11,
            ipaIconDp = 30, imageWeight = 0.20f, optionsWeight = 0.44f
        )
        else -> QuizLayoutMetrics(
            lemmaSp = 16, lemmaMaxLines = 3, metaSp = 10,
            exampleSp = 10, exampleMaxLines = 4, optionSp = 10,
            ipaIconDp = 28, imageWeight = 0.16f, optionsWeight = 0.46f
        )
    }
}

@Composable
private fun OptionGridCompact(
    options: List<String>,
    wrongIndices: Set<Int>,
    onSelect: (Int) -> Unit,
    optionTextSp: Int = 12,
    modifier: Modifier = Modifier
) {
    Column(modifier = modifier, verticalArrangement = Arrangement.spacedBy(6.dp)) {
        options.chunked(2).forEachIndexed { rowIndex, row ->
            Row(
                Modifier.fillMaxWidth().weight(1f),
                horizontalArrangement = Arrangement.spacedBy(6.dp)
            ) {
                row.forEachIndexed { colIndex, text ->
                    val i = rowIndex * 2 + colIndex
                    val wrong = i in wrongIndices
                    Box(
                        Modifier
                            .weight(1f)
                            .fillMaxHeight()
                            .pressableScale(enabled = !wrong) { onSelect(i) }
                            .clip(RoundedCornerShape(12.dp))
                            .background(if (wrong) WrongRed else CardBlue)
                            .border(
                                1.dp,
                                if (wrong) Color(0xFFE57373) else Color(0xFFB7D3EA),
                                RoundedCornerShape(12.dp)
                            )
                            .padding(horizontal = 6.dp, vertical = 4.dp),
                        contentAlignment = Alignment.Center
                    ) {
                        Text(
                            text,
                            textAlign = TextAlign.Center,
                            fontSize = optionTextSp.sp,
                            lineHeight = (optionTextSp + 3).sp,
                            maxLines = 4,
                            softWrap = true,
                            overflow = TextOverflow.Ellipsis,
                            color = if (wrong) Color(0xFFB71C1C) else Color.Black
                        )
                    }
                }
                if (row.size == 1) Spacer(Modifier.weight(1f))
            }
        }
    }
}

@Composable
fun WordDetailScreen(
    word: Word,
    imageFile: File?,
    autoPlayToken: Int,
    onPlayWord: () -> Unit,
    onPlaySentence: () -> Unit,
    onEasy: () -> Unit,
    onContinue: () -> Unit,
    onBack: () -> Unit,
    continueLabel: String = "继续",
    autoPlay: Boolean = true,
    isEasy: Boolean = false,
    onUnchop: (() -> Unit)? = null
) {
    LaunchedEffect(autoPlayToken, word.id) {
        if (autoPlay) onPlaySentence()
    }

    Scaffold(
        containerColor = Bg,
        bottomBar = {
            DetailDiagonalActionBar(
                isEasy = isEasy,
                onEasy = onEasy,
                onUnchop = onUnchop,
                continueLabel = continueLabel,
                onContinue = onContinue
            )
        }
    ) { padding ->
        Column(
            Modifier
                .padding(padding)
                .padding(horizontal = 16.dp)
                .fillMaxSize()
                .verticalScroll(rememberScrollState())
        ) {
            Spacer(Modifier.height(8.dp))
            val lemmaStyle = remember(word.lemma) { detailLemmaStyle(word.lemma) }
            SelectionContainer {
                Text(
                    word.lemma,
                    fontSize = lemmaStyle.fontSp.sp,
                    lineHeight = lemmaStyle.lineSp.sp,
                    fontWeight = FontWeight.Bold,
                    softWrap = true,
                    modifier = Modifier.fillMaxWidth()
                )
            }
            Spacer(Modifier.height(4.dp))
            Row(verticalAlignment = Alignment.CenterVertically) {
                IconButton(onClick = onPlayWord) {
                    Icon(Icons.AutoMirrored.Filled.VolumeUp, contentDescription = "发音")
                }
                Text(
                    "/${word.ipa}/",
                    color = Color.Gray,
                    fontSize = 14.sp,
                    maxLines = 1,
                    overflow = TextOverflow.Ellipsis,
                    modifier = Modifier.weight(1f)
                )
                Text(word.level, color = Accent, fontWeight = FontWeight.Bold, fontSize = 13.sp)
            }
            SelectionContainer {
                Text(
                    word.detailDefLine,
                    fontSize = 16.sp,
                    lineHeight = 22.sp,
                    fontWeight = FontWeight.SemiBold,
                    softWrap = true
                )
            }
            Spacer(Modifier.height(12.dp))
            if (imageFile != null) {
                AsyncImage(
                    model = imageFile,
                    contentDescription = null,
                    contentScale = ContentScale.Crop,
                    modifier = Modifier
                        .fillMaxWidth()
                        .heightIn(max = 180.dp)
                        .clip(RoundedCornerShape(12.dp))
                )
                Spacer(Modifier.height(12.dp))
            }
            Card(
                colors = CardDefaults.cardColors(containerColor = Color.White),
                shape = RoundedCornerShape(14.dp),
                modifier = Modifier.fillMaxWidth()
            ) {
                Column(Modifier.padding(14.dp)) {
                    Text("例句", fontWeight = FontWeight.Bold, color = Accent)
                    Spacer(Modifier.height(8.dp))
                    if (word.exampleDe.isNotBlank()) {
                        Row(verticalAlignment = Alignment.Top) {
                            IconButton(onClick = onPlaySentence, modifier = Modifier.size(32.dp)) {
                                Icon(
                                    Icons.AutoMirrored.Filled.VolumeUp,
                                    contentDescription = "例句发音",
                                    modifier = Modifier.size(18.dp)
                                )
                            }
                            SelectionContainer {
                                Column {
                                    Text(word.exampleDe, fontSize = 15.sp, softWrap = true)
                                    val zh = word.exampleZhDisplay
                                    if (zh.isNotBlank()) {
                                        Spacer(Modifier.height(4.dp))
                                        Text(zh, color = Color(0xFF555555), fontSize = 14.sp, softWrap = true)
                                    }
                                    if (word.exampleEn.isNotBlank()) {
                                        Spacer(Modifier.height(2.dp))
                                        Text(
                                            word.exampleEn,
                                            color = Color(0xFF777777),
                                            fontSize = 13.sp,
                                            softWrap = true
                                        )
                                    }
                                }
                            }
                        }
                    } else {
                        Text("暂无例句", color = Color.Gray)
                    }
                }
            }
            Spacer(Modifier.height(24.dp))
        }
    }
}
