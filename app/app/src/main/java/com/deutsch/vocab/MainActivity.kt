package com.deutsch.vocab

import android.os.Bundle
import androidx.activity.ComponentActivity
import androidx.activity.compose.setContent
import androidx.activity.enableEdgeToEdge
import androidx.compose.animation.AnimatedContent
import androidx.compose.animation.fadeIn
import androidx.compose.animation.fadeOut
import androidx.compose.animation.slideInHorizontally
import androidx.compose.animation.slideOutHorizontally
import androidx.compose.animation.togetherWith
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Surface
import androidx.compose.material3.lightColorScheme
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Color
import androidx.lifecycle.viewmodel.compose.viewModel
import com.deutsch.vocab.data.PackRepository
import com.deutsch.vocab.ui.DeckHomeScreen
import com.deutsch.vocab.ui.DeckListScreen
import com.deutsch.vocab.ui.FastOffsetTween
import com.deutsch.vocab.ui.FastTween
import com.deutsch.vocab.ui.QuizScreen
import com.deutsch.vocab.ui.QuizViewModel

sealed interface Route {
    data object Home : Route
    data class Deck(val level: String) : Route
    data class Quiz(val level: String) : Route
}

class MainActivity : ComponentActivity() {
    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        enableEdgeToEdge()
        val repo = PackRepository(applicationContext)
        setContent {
            MaterialTheme(
                colorScheme = lightColorScheme(
                    primary = Color(0xFF1A56DB),
                    background = Color(0xFFEAF3FB)
                )
            ) {
                Surface(Modifier.fillMaxSize()) {
                    var route by remember { mutableStateOf<Route>(Route.Home) }
                    val quizVm: QuizViewModel = viewModel()
                    AnimatedContent(
                        targetState = route,
                        transitionSpec = {
                            val forward = targetState !is Route.Home && initialState is Route.Home ||
                                targetState is Route.Quiz
                            if (forward) {
                                (fadeIn(FastTween) + slideInHorizontally(FastOffsetTween) { it / 5 }) togetherWith
                                    (fadeOut(FastTween) + slideOutHorizontally(FastOffsetTween) { -it / 6 })
                            } else {
                                (fadeIn(FastTween) + slideInHorizontally(FastOffsetTween) { -it / 5 }) togetherWith
                                    (fadeOut(FastTween) + slideOutHorizontally(FastOffsetTween) { it / 6 })
                            }
                        },
                        label = "rootNav"
                    ) { r ->
                        when (r) {
                            Route.Home -> DeckListScreen(
                                repo = repo,
                                onOpenDeck = { route = Route.Deck(it) },
                                onImported = {}
                            )
                            is Route.Deck -> DeckHomeScreen(
                                repo = repo,
                                level = r.level,
                                onBack = { route = Route.Home },
                                onStartQuiz = { route = Route.Quiz(r.level) }
                            )
                            is Route.Quiz -> QuizScreen(
                                vm = quizVm,
                                level = r.level,
                                onBack = { route = Route.Deck(r.level) }
                            )
                        }
                    }
                }
            }
        }
    }
}
