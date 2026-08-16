// State Variables
let currentQuestions = [];
let currentQuestionIndex = 0;
let userAnswers = {}; // key: question index, value: selected option key (e.g. 'A')
let mode = 'practice';
let isExamFinished = false;
let timerInterval = null;
let timeRemaining = 0;
let isRetryMode = false;

// DOM Elements
const views = {
  dashboard: document.getElementById('view-dashboard'),
  loading: document.getElementById('view-loading'),
  quiz: document.getElementById('view-quiz'),
  results: document.getElementById('view-results')
};

const elements = {
  chapterList: document.getElementById('chapter-list'),
  modeRadios: document.getElementsByName('quiz-mode'),
  modeIndicator: document.getElementById('mode-indicator'),
  modeText: document.getElementById('mode-text'),
  
  // Quiz Header
  btnBack: document.getElementById('btn-back-dashboard'),
  questionCounter: document.getElementById('question-counter'),
  scoreTracker: document.getElementById('score-tracker'),
  timerDisplay: document.getElementById('timer-display'),
  btnToggleNav: document.getElementById('btn-toggle-navigator'),
  
  // Question Area
  questionText: document.getElementById('question-text'),
  questionImageContainer: document.getElementById('question-image-container'),
  questionImage: document.getElementById('question-image'),
  optionsContainer: document.getElementById('options-container'),
  
  // Feedback
  feedbackSection: document.getElementById('feedback-section'),
  feedbackBadge: document.getElementById('feedback-badge'),
  hintContainer: document.getElementById('hint-container'),
  hintText: document.getElementById('hint-text'),
  explanationContainer: document.getElementById('explanation-container'),
  explanationText: document.getElementById('explanation-text'),
  
  // Actions
  btnPrev: document.getElementById('btn-prev'),
  btnNext: document.getElementById('btn-next'),
  btnCheckAnswer: document.getElementById('btn-check-answer'),
  btnShowHint: document.getElementById('btn-show-hint'),
  btnFinish: document.getElementById('btn-finish'),
  
  // Navigator
  navOverlay: document.getElementById('navigator-overlay'),
  navGrid: document.getElementById('navigator-grid'),
  btnCloseNav: document.getElementById('btn-close-navigator'),
  
  // Results
  finalScore: document.getElementById('final-score'),
  scorePercentage: document.getElementById('score-percentage'),
  btnRetry: document.getElementById('btn-retry-incorrect'),
  btnReturnHome: document.getElementById('btn-return-home')
};

// Initialize Dashboard
function initDashboard() {
  elements.chapterList.innerHTML = '';
  if (typeof chapterIndex !== 'undefined') {
    chapterIndex.forEach(chapter => {
      const card = document.createElement('div');
      card.className = 'chapter-card';
      card.innerHTML = `
        <div>
          <h3>${chapter.title}</h3>
          <p>${chapter.questionCount} Questions</p>
        </div>
        <button class="btn btn-primary btn-start-chapter" data-file="${chapter.file}">Start Practice</button>
      `;
      elements.chapterList.appendChild(card);
    });

    document.querySelectorAll('.btn-start-chapter').forEach(btn => {
      btn.addEventListener('click', (e) => {
        const file = e.target.getAttribute('data-file');
        loadChapter(file);
      });
    });
  } else {
    elements.chapterList.innerHTML = '<div class="error">Failed to load chapter index.</div>';
  }
}

// Load Chapter Data dynamically
function loadChapter(filename) {
  // Determine Mode
  const selectedMode = Array.from(elements.modeRadios).find(r => r.checked).value;
  mode = selectedMode;
  elements.modeText.innerText = mode.charAt(0).toUpperCase() + mode.slice(1);
  elements.modeIndicator.classList.remove('hidden');

  switchView('loading');
  
  // If already loaded, use it
  if (window.olympiadData && window.olympiadData[filename]) {
    startQuiz(window.olympiadData[filename]);
    return;
  }

  // Inject script to load chunk
  const script = document.createElement('script');
  script.src = `data/${filename}`;
  script.onload = () => {
    startQuiz(window.olympiadData[filename]);
  };
  script.onerror = () => {
    alert("Failed to load chapter data. Are you sure the files are present?");
    switchView('dashboard');
  };
  document.body.appendChild(script);
}

// Start Quiz
function startQuiz(questions) {
  currentQuestions = questions;
  currentQuestionIndex = 0;
  userAnswers = {};
  isExamFinished = false;
  isRetryMode = false;
  
  setupQuizUI();
  renderQuestion();
  switchView('quiz');
  
  if (mode === 'exam') {
    // 1 minute per question
    startTimer(currentQuestions.length * 60);
  }
}

function setupQuizUI() {
  if (mode === 'practice') {
    elements.scoreTracker.classList.remove('hidden');
    elements.timerDisplay.classList.add('hidden');
    elements.btnFinish.classList.add('hidden');
    updateScoreTracker();
  } else {
    elements.scoreTracker.classList.add('hidden');
    elements.timerDisplay.classList.remove('hidden');
    elements.btnFinish.classList.remove('hidden');
  }
  buildNavigator();
}

function renderQuestion() {
  const q = currentQuestions[currentQuestionIndex];
  
  elements.questionCounter.innerText = `Question ${currentQuestionIndex + 1} of ${currentQuestions.length}`;
  elements.questionText.innerText = q.question || "";
  
  // Handle image
  if (q.has_graphic && q.page_image) {
    elements.questionImage.src = q.page_image;
    elements.questionImageContainer.classList.remove('hidden');
  } else {
    elements.questionImage.src = "";
    elements.questionImageContainer.classList.add('hidden');
  }
  
  // Render Options
  elements.optionsContainer.innerHTML = '';
  const options = q.options || {};
  const isAnswered = userAnswers[currentQuestionIndex] !== undefined;
  const selectedKey = userAnswers[currentQuestionIndex];
  
  for (const [key, text] of Object.entries(options)) {
    const optDiv = document.createElement('div');
    optDiv.className = 'option-card';
    
    // In practice mode, if it's answered, lock options and highlight correct/incorrect
    if (mode === 'practice' && isAnswered) {
      optDiv.classList.add('locked');
      if (key === q.correct_answer) {
        optDiv.classList.add('correct');
      } else if (key === selectedKey) {
        optDiv.classList.add('incorrect');
      }
    } else if (mode === 'exam' && (isExamFinished || isAnswered)) {
      if (key === selectedKey) optDiv.classList.add('selected');
      if (isExamFinished) {
        optDiv.classList.add('locked');
        if (key === q.correct_answer) optDiv.classList.add('correct');
        else if (key === selectedKey) optDiv.classList.add('incorrect');
      }
    }
    
    optDiv.innerHTML = `<span class="option-label">${key}.</span><span class="option-text">${text}</span>`;
    
    optDiv.addEventListener('click', () => {
      if ((mode === 'practice' && isAnswered) || isExamFinished) return;
      selectOption(key);
    });
    
    elements.optionsContainer.appendChild(optDiv);
  }
  
  updateButtons();
  updateFeedbackSection();
  updateNavigatorHighlight();
}

function selectOption(key) {
  userAnswers[currentQuestionIndex] = key;
  
  if (mode === 'practice') {
    // Immediate check
    const q = currentQuestions[currentQuestionIndex];
    if (q.correct_answer && key === q.correct_answer) {
      // Play a tiny subtle sound maybe? Or just visual
    }
    updateScoreTracker();
    updateNavigatorState(currentQuestionIndex);
    renderQuestion(); // Re-render to show correct/incorrect
  } else {
    // Exam mode, just highlight selection
    renderQuestion();
    updateNavigatorState(currentQuestionIndex);
  }
}

function updateButtons() {
  elements.btnPrev.disabled = currentQuestionIndex === 0;
  elements.btnNext.disabled = currentQuestionIndex === currentQuestions.length - 1;
  
  const q = currentQuestions[currentQuestionIndex];
  const isAnswered = userAnswers[currentQuestionIndex] !== undefined;
  
  if (mode === 'practice') {
    elements.btnCheckAnswer.classList.add('hidden'); // We check immediately on click
    elements.btnShowHint.classList.toggle('hidden', isAnswered || (!q.hint && !q.explanation));
  } else {
    elements.btnShowHint.classList.add('hidden');
    elements.btnCheckAnswer.classList.add('hidden');
    if (currentQuestionIndex === currentQuestions.length - 1 && !isExamFinished) {
      elements.btnFinish.classList.remove('hidden');
    }
  }
}

function updateFeedbackSection() {
  const q = currentQuestions[currentQuestionIndex];
  const isAnswered = userAnswers[currentQuestionIndex] !== undefined;
  
  elements.feedbackSection.classList.add('hidden');
  elements.feedbackBadge.className = 'feedback-badge hidden';
  elements.hintContainer.classList.add('hidden');
  elements.explanationContainer.classList.add('hidden');
  
  if (mode === 'practice' && isAnswered) {
    elements.feedbackSection.classList.remove('hidden');
    elements.feedbackBadge.classList.remove('hidden');
    
    const isCorrect = userAnswers[currentQuestionIndex] === q.correct_answer;
    if (isCorrect) {
      elements.feedbackBadge.innerText = '✅ Correct!';
      elements.feedbackBadge.classList.add('correct');
    } else {
      elements.feedbackBadge.innerText = `❌ Incorrect. Correct answer is ${q.correct_answer}`;
      elements.feedbackBadge.classList.add('incorrect');
    }
    
    if (q.explanation) {
      elements.explanationText.innerText = q.explanation;
      elements.explanationContainer.classList.remove('hidden');
    }
  } else if (mode === 'exam' && isExamFinished) {
    elements.feedbackSection.classList.remove('hidden');
    if (q.explanation) {
      elements.explanationText.innerText = q.explanation;
      elements.explanationContainer.classList.remove('hidden');
    }
  }
}

// Navigation Actions
elements.btnPrev.addEventListener('click', () => {
  if (currentQuestionIndex > 0) {
    currentQuestionIndex--;
    renderQuestion();
  }
});

elements.btnNext.addEventListener('click', () => {
  if (currentQuestionIndex < currentQuestions.length - 1) {
    currentQuestionIndex++;
    renderQuestion();
  }
});

elements.btnBack.addEventListener('click', () => {
  if (confirm("Are you sure you want to return to the dashboard? Your progress will be lost.")) {
    stopTimer();
    switchView('dashboard');
    elements.modeIndicator.classList.add('hidden');
  }
});

elements.btnShowHint.addEventListener('click', () => {
  const q = currentQuestions[currentQuestionIndex];
  elements.feedbackSection.classList.remove('hidden');
  if (q.hint) {
    elements.hintText.innerText = q.hint;
    elements.hintContainer.classList.remove('hidden');
  } else if (q.explanation) {
    elements.explanationText.innerText = q.explanation;
    elements.explanationContainer.classList.remove('hidden');
  }
  elements.btnShowHint.classList.add('hidden');
});

elements.btnFinish.addEventListener('click', finishExam);

// Question Navigator
function buildNavigator() {
  elements.navGrid.innerHTML = '';
  currentQuestions.forEach((q, index) => {
    const btn = document.createElement('button');
    btn.className = 'nav-btn';
    btn.innerText = index + 1;
    btn.addEventListener('click', () => {
      currentQuestionIndex = index;
      renderQuestion();
      elements.navOverlay.classList.add('hidden');
    });
    elements.navGrid.appendChild(btn);
  });
}

function updateNavigatorHighlight() {
  const btns = elements.navGrid.children;
  for (let i = 0; i < btns.length; i++) {
    btns[i].classList.toggle('current', i === currentQuestionIndex);
  }
}

function updateNavigatorState(index) {
  const btn = elements.navGrid.children[index];
  const q = currentQuestions[index];
  const ans = userAnswers[index];
  
  if (ans !== undefined) {
    if (mode === 'practice' || isExamFinished) {
      if (ans === q.correct_answer) {
        btn.classList.add('correct');
      } else {
        btn.classList.add('incorrect');
      }
    } else {
      btn.classList.add('answered');
    }
  }
}

elements.btnToggleNav.addEventListener('click', () => {
  elements.navOverlay.classList.remove('hidden');
});
elements.btnCloseNav.addEventListener('click', () => {
  elements.navOverlay.classList.add('hidden');
});

// Scoring and Exam Logic
function updateScoreTracker() {
  let correct = 0;
  for (let i = 0; i < currentQuestions.length; i++) {
    if (userAnswers[i] === currentQuestions[i].correct_answer) correct++;
  }
  elements.scoreTracker.innerText = `Score: ${correct} / ${Object.keys(userAnswers).length}`;
}

function startTimer(seconds) {
  timeRemaining = seconds;
  updateTimerDisplay();
  
  if (timerInterval) clearInterval(timerInterval);
  timerInterval = setInterval(() => {
    timeRemaining--;
    updateTimerDisplay();
    if (timeRemaining <= 0) {
      clearInterval(timerInterval);
      alert("Time is up!");
      finishExam();
    }
  }, 1000);
}

function stopTimer() {
  if (timerInterval) clearInterval(timerInterval);
}

function updateTimerDisplay() {
  const m = Math.floor(timeRemaining / 60).toString().padStart(2, '0');
  const s = (timeRemaining % 60).toString().padStart(2, '0');
  elements.timerDisplay.innerText = `${m}:${s}`;
  if (timeRemaining < 60) elements.timerDisplay.classList.add('danger');
  else elements.timerDisplay.classList.remove('danger');
}

function finishExam() {
  stopTimer();
  isExamFinished = true;
  
  let correct = 0;
  let incorrectQuestions = [];
  
  for (let i = 0; i < currentQuestions.length; i++) {
    const q = currentQuestions[i];
    const ans = userAnswers[i];
    updateNavigatorState(i);
    
    if (ans === q.correct_answer) {
      correct++;
    } else {
      incorrectQuestions.push(q);
    }
  }
  
  const total = currentQuestions.length;
  const perc = Math.round((correct / total) * 100);
  
  elements.finalScore.innerText = `${correct}/${total}`;
  elements.scorePercentage.innerText = `${perc}%`;
  
  if (incorrectQuestions.length > 0) {
    elements.btnRetry.classList.remove('hidden');
    elements.btnRetry.onclick = () => {
      isRetryMode = true;
      startQuiz(incorrectQuestions);
    };
  } else {
    elements.btnRetry.classList.add('hidden');
  }
  
  switchView('results');
}

elements.btnReturnHome.addEventListener('click', () => {
  elements.modeIndicator.classList.add('hidden');
  switchView('dashboard');
});

// View Routing
function switchView(viewId) {
  for (const v in views) {
    views[v].classList.add('hidden');
    views[v].classList.remove('active');
  }
  views[viewId].classList.remove('hidden');
  views[viewId].classList.add('active');
}

// Init
window.addEventListener('DOMContentLoaded', initDashboard);
