const state = {
  chapterId: 1,
  questionIndex: 0,
  answers: {},
  mode: 'practice',
  studentName: 'Student',
  started: false,
  questions: [],
  timeLeft: 1200,
  timerInterval: null,
  examSubmitted: false
};

const chapterSelect = document.getElementById('startChapterSelect');
const questionCard = document.getElementById('questionCard');
const prevBtn = document.getElementById('prevBtn');
const nextBtn = document.getElementById('nextBtn');
const resetQuizBtn = document.getElementById('resetQuizBtn');
const welcomeTitle = document.getElementById('welcomeTitle');
const startScreen = document.getElementById('startScreen');
const quizScreen = document.getElementById('quizScreen');
const studentNameInput = document.getElementById('studentNameInput');
const startQuizBtn = document.getElementById('startQuizBtn');
const progressText = document.getElementById('progressText');
const progressFill = document.getElementById('progressFill');
const timerDisplay = document.getElementById('timerDisplay');
const timerContainer = document.getElementById('timerContainer');
const studentNameStorageKey = 'olympiadStudentName';

function getSelectedChapter() {
  return chapterIndex.find((chapter) => chapter.id === state.chapterId) || chapterIndex[0];
}

function getSelectedQuestions() {
  const chapter = getSelectedChapter();
  const allQuestions = window.olympiadData?.[chapter.file] || [];
  return state.mode === 'exam' && state.questions.length > 0 ? state.questions : allQuestions;
}

function getAnswerKey(chapterId, questionId) {
  return `${chapterId}:${questionId}`;
}

function getRandomQuestions(questions, max = 15) {
  const shuffled = [...questions].sort(() => Math.random() - 0.5);
  return shuffled.slice(0, Math.min(max, shuffled.length));
}

function startTimer() {
  if (state.timerInterval) clearInterval(state.timerInterval);
  
  state.timerInterval = setInterval(() => {
    state.timeLeft--;
    updateTimerDisplay();
    
    if (state.timeLeft <= 0) {
      clearInterval(state.timerInterval);
      submitExam();
    }
  }, 1000);
}

function updateTimerDisplay() {
  const minutes = Math.floor(state.timeLeft / 60);
  const seconds = state.timeLeft % 60;
  timerDisplay.textContent = String(minutes).padStart(2, '0') + ':' + String(seconds).padStart(2, '0');
  
  if (state.timeLeft <= 300) {
    timerContainer.classList.add('warning');
  } else {
    timerContainer.classList.remove('warning');
  }
}

function stopTimer() {
  if (state.timerInterval) {
    clearInterval(state.timerInterval);
    state.timerInterval = null;
  }
}

function renderChapterOptions() {
  chapterSelect.innerHTML = chapterIndex
    .map((chapter) => '<option value="' + chapter.id + '">' + chapter.title + '</option>')
    .join('');
  chapterSelect.value = String(state.chapterId);
}

function computeChapterScore(chapterId, questions) {
  return questions.reduce((total, question) => {
    const answerKey = getAnswerKey(chapterId, question.id);
    return total + (state.answers[answerKey] === question.correct_answer ? 1 : 0);
  }, 0);
}

function getCurrentAnswerKey(questions) {
  const chapter = getSelectedChapter();
  const question = questions[state.questionIndex];
  return question ? getAnswerKey(chapter.id, question.id) : '';
}

function getExamResultMessage(percentage) {
  if (percentage >= 90) {
    return {
      title: 'Outstanding work, ' + state.studentName + '!',
      message: 'You mastered this exam. Keep challenging yourself with the next chapter.'
    };
  }

  if (percentage >= 70) {
    return {
      title: 'Great job, ' + state.studentName + '!',
      message: 'You have a strong score. A little revision can push it even higher.'
    };
  }

  if (percentage >= 50) {
    return {
      title: 'Good effort, ' + state.studentName + '!',
      message: 'You are getting there. Review the tricky questions and try again.'
    };
  }

  return {
    title: 'Keep practicing, ' + state.studentName + '!',
    message: 'Every attempt helps. Revisit this chapter once more and build from there.'
  };
}

function updateProgress(questions) {
  const total = questions.length || 1;
  const current = state.questionIndex + 1;
  const percentage = (current / total) * 100;
  
  progressText.textContent = 'Question ' + current + ' of ' + total;
  progressFill.style.width = percentage + '%';
}

function updateModeUI() {
  const modeText = state.mode === 'exam' ? 'Exam' : 'Practice';
  welcomeTitle.textContent = state.studentName + "'s " + modeText + ' Quiz';
  
  if (state.mode === 'exam') {
    timerContainer.classList.remove('hidden');
  } else {
    timerContainer.classList.add('hidden');
  }
}

function renderQuestion() {
  if (state.examSubmitted) return;
  
  const chapter = getSelectedChapter();
  const questions = getSelectedQuestions();

  if (!questions.length) {
    questionCard.innerHTML = '<div class="empty-state">No questions found for this chapter.</div>';
    return;
  }

  if (state.questionIndex < 0) state.questionIndex = 0;
  if (state.questionIndex >= questions.length) state.questionIndex = questions.length - 1;

  const question = questions[state.questionIndex];
  const answerKey = getAnswerKey(chapter.id, question.id);
  const selectedAnswer = state.answers[answerKey];
  const options = Object.entries(question.options || {});
  const isPracticeMode = state.mode === 'practice';
  const isAnswered = selectedAnswer !== undefined;

  let statusText = '';
  if (isAnswered) {
    if (isPracticeMode) {
      statusText = selectedAnswer === question.correct_answer
        ? '<div class="answer-status correct">Correct answer</div>'
        : '<div class="answer-status incorrect">Incorrect. The correct answer is ' + question.correct_answer + '.</div>';
    } else {
      statusText = '<div class="answer-status saved">Answer saved</div>';
    }
  }

  let optionMarkup = options
    .map(([key, value]) => {
      const isSelected = selectedAnswer === key;
      const isCorrect = key === question.correct_answer;
      const classes = [
        'option-btn',
        isSelected ? 'selected' : '',
        isAnswered && isPracticeMode && isCorrect ? 'correct' : '',
        isAnswered && isPracticeMode && isSelected && !isCorrect ? 'incorrect' : ''
      ].filter(Boolean).join(' ');

      return '<button class="' + classes + '" type="button" data-option="' + key + '" aria-label="Answer ' + key + '"><span class="letter">' + key + '</span><span class="option-text">' + value + '</span></button>';
    })
    .join('');

  let imageMarkup = question.has_graphic && question.page_image
    ? '<img class="question-image" src="' + question.page_image + '" alt="' + (question.graphic_description || 'Question illustration') + '" />'
    : '';

  let explanationMarkup =
    isPracticeMode && isAnswered && question.explanation
      ? '<div class="explanation-box"><strong>Explanation:</strong> ' + question.explanation + '</div>'
      : '';

  questionCard.innerHTML = '<div class="question-meta"><span class="question-tag">' + chapter.title + '</span><span>' + (state.questionIndex + 1) + ' / ' + questions.length + '</span></div><h2 class="question-title">' + question.question + '</h2>' + imageMarkup + '<div class="options-list">' + optionMarkup + '</div>' + statusText + explanationMarkup;

  questionCard.querySelectorAll('.option-btn').forEach((button) => {
    button.addEventListener('click', () => {
      const option = button.dataset.option;
      state.answers[answerKey] = option;
      renderQuestion();
    });
  });

  updateProgress(questions);
  updateButtonStates(questions);
}

function updateButtonStates(questions) {
  const isLastQuestion = state.questionIndex >= questions.length - 1;
  const answerKey = getCurrentAnswerKey(questions);
  const hasSelectedAnswer = answerKey ? state.answers[answerKey] !== undefined : false;
  
  prevBtn.disabled = state.questionIndex === 0;
  nextBtn.disabled = !hasSelectedAnswer;
  
  if (state.mode === 'exam') {
    nextBtn.textContent = isLastQuestion ? 'Submit Exam' : 'Next';
  } else {
    nextBtn.textContent = isLastQuestion ? 'Summary' : 'Next';
  }
}

function resetCurrentChapter() {
  state.questionIndex = 0;
  state.answers = {};
  state.examSubmitted = false;
  
  if (state.mode === 'exam') {
    stopTimer();
    state.timeLeft = 1200;
    startTimer();
  }
  
  renderQuestion();
}

function submitExam() {
  stopTimer();
  state.examSubmitted = true;
  const questions = getSelectedQuestions();
  const score = computeChapterScore(state.chapterId, questions);
  const total = questions.length;
  const percentage = Math.round((score / total) * 100);
  const resultMessage = getExamResultMessage(percentage);
  
  prevBtn.disabled = true;
  nextBtn.disabled = true;
  chapterSelect.disabled = true;
  
  questionCard.innerHTML = '<div class="question-meta"><span class="question-tag">' + getSelectedChapter().title + '</span><span>Exam Completed</span></div><div class="exam-results"><p class="result-kicker">Congratulations</p><h2 class="question-title">' + resultMessage.title + '</h2><div class="score-display">' + score + '/' + total + '</div><div class="result-summary"><strong>Score: ' + percentage + '%</strong><br>You answered ' + score + ' out of ' + total + ' questions correctly.</div><p class="result-message">' + resultMessage.message + '</p><button id="retryBtn" class="primary-btn retry-btn" type="button">Try Another Chapter</button></div>';
  
  document.getElementById('retryBtn').addEventListener('click', () => {
    location.reload();
  });
}

function showPracticeSummary(questions) {
  const score = computeChapterScore(state.chapterId, questions);
  const total = questions.length;
  const percentage = Math.round((score / total) * 100);

  questionCard.innerHTML = '<div class="question-meta"><span class="question-tag">' + getSelectedChapter().title + '</span><span>Practice Summary</span></div><div class="exam-results"><h2 class="question-title">Practice Complete!</h2><div class="score-display">' + score + '/' + total + '</div><div class="result-summary"><strong>Score: ' + percentage + '%</strong><br>You answered ' + score + ' out of ' + total + ' questions correctly.</div><button id="retryBtn" class="primary-btn" style="margin-top: 16px; width: 100%; max-width: 200px;">Try Again</button></div>';
  
  prevBtn.disabled = true;
  nextBtn.disabled = true;
  
  document.getElementById('retryBtn').addEventListener('click', () => {
    state.questionIndex = 0;
    state.answers = {};
    state.examSubmitted = false;
    prevBtn.disabled = false;
    nextBtn.disabled = false;
    renderQuestion();
  });
}

function changeChapter(chapterId) {
  state.chapterId = Number(chapterId);
  state.questionIndex = 0;
  state.answers = {};
  state.examSubmitted = false;
  
  if (state.mode === 'exam') {
    stopTimer();
    state.timeLeft = 1200;
    const allQuestions = window.olympiadData?.[getSelectedChapter().file] || [];
    state.questions = getRandomQuestions(allQuestions, 15);
    startTimer();
  }
  
  renderQuestion();
}

function startQuiz() {
  const enteredName = studentNameInput.value.trim();
  state.studentName = enteredName || 'Student';
  localStorage.setItem(studentNameStorageKey, state.studentName);
  state.mode = document.querySelector('input[name="quizMode"]:checked')?.value || 'practice';
  state.chapterId = Number(chapterSelect.value) || state.chapterId;
  state.started = true;
  state.examSubmitted = false;
  
  startScreen.classList.add('hidden');
  quizScreen.classList.remove('hidden');
  
  renderChapterOptions();
  updateModeUI();
  
  if (state.mode === 'exam') {
    const allQuestions = window.olympiadData?.[getSelectedChapter().file] || [];
    state.questions = getRandomQuestions(allQuestions, 15);
    state.timeLeft = 1200;
    startTimer();
  }
  
  renderQuestion();
}

function attachEvents() {
  chapterSelect.addEventListener('change', (event) => changeChapter(event.target.value));

  prevBtn.addEventListener('click', () => {
    const questions = getSelectedQuestions();
    if (!questions.length) return;
    state.questionIndex = Math.max(0, state.questionIndex - 1);
    renderQuestion();
  });

  nextBtn.addEventListener('click', () => {
    const questions = getSelectedQuestions();
    if (!questions.length) return;
    const answerKey = getCurrentAnswerKey(questions);
    if (!answerKey || state.answers[answerKey] === undefined) return;
    
    const isLastQuestion = state.questionIndex >= questions.length - 1;
    
    if (isLastQuestion) {
      if (state.mode === 'exam') {
        submitExam();
      } else {
        showPracticeSummary(questions);
      }
      return;
    }
    
    state.questionIndex = Math.min(questions.length - 1, state.questionIndex + 1);
    renderQuestion();
  });

  resetQuizBtn.addEventListener('click', resetCurrentChapter);
  startQuizBtn.addEventListener('click', startQuiz);
  studentNameInput.addEventListener('input', () => {
    localStorage.setItem(studentNameStorageKey, studentNameInput.value.trim());
  });
}

function init() {
  const savedName = localStorage.getItem(studentNameStorageKey);
  if (savedName) {
    state.studentName = savedName;
    studentNameInput.value = savedName;
  }

  renderChapterOptions();
  attachEvents();
  updateModeUI();
}

init();
