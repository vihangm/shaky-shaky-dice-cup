var u = new URL(window.location)
u.protocol = u.protocol == "https:" ? 'wss://' : 'ws://';
u.pathname = '/play';

var webSocketUri = u.href;
var websocket = new WebSocket(webSocketUri);

var players = [];
var currentPlayer = '';
var diceRollCount = 0;
var lastPersonToRoll = '';
var lastPersonToPeek = '';
var dice = [null, null];

var updateState = function(stateStr) {
  var formEl = document.querySelector('#form');
  var diceEl = document.querySelector('#dice');
  var playersEl = document.querySelector('#players');
  var currentPlayerEl = document.querySelector('#currentPlayer');
  var diceRollerEl = document.querySelector('#diceRoller');
  var dicePeekerEl = document.querySelector('#dicePeeker');

  state = JSON.parse(stateStr);
  if (state['player_name_for_client'] && state['player_name_for_client'] != '') {
    formEl.name.value = state['player_name_for_client'];
    if (formEl.querySelector('button')) {
      formEl.querySelector('input#name').setAttribute('readonly', 'readonly')
      formEl.querySelector('button').remove();
    }
  }
  if (state['dice']) {
    diceEl.innerHTML = state['dice'];
  } else if (state['dice_roll_count'] != diceRollCount) {
    diceEl.innerHTML = 'SECRETSSSSSSS!'
  }
  diceRollCount = state['dice_roll_count'];

  playersEl.innerHTML = state['players'];
  currentPlayerEl.innerHTML = state['current_player'];
  diceRollerEl.innerHTML = state['last_person_to_roll_dice'];
  dicePeekerEl.innerHTML = state['last_person_to_peek_at_dice'];

  var enableButtons = state['current_player'] == formEl.name.value;
  document.querySelectorAll('.modifiers').forEach(function(b) { b.disabled = !enableButtons; });
};

websocket.onopen = function() {
  console.log('Connected');
  websocket.send(JSON.stringify({'method': 'init_state'}));
};

websocket.onclose = function() {
  console.log('Closed');
};

websocket.onmessage = function(e) {
  console.log('Message received');
  console.log(e.data);
  updateState(e.data);
};

websocket.onerror = function(e) {
  console.log(e);
};

var submitFormAjax = function(e) {
  e.preventDefault();
  websocket.send(JSON.stringify({
    'method': 'set_name',
    'name': e.target.name.value,
  }));
  return false;
};

var passLeft = function(e) {
  e.preventDefault();
  websocket.send(JSON.stringify({'method': 'pass_left'}));
};

var passRight = function(e) {
  e.preventDefault();
  websocket.send(JSON.stringify({'method': 'pass_right'}));
};

var rollDice = function(e) {
  e.preventDefault();
  websocket.send(JSON.stringify({'method': 'roll_dice'}));
};

var peekDice = function(e) {
  e.preventDefault();
  websocket.send(JSON.stringify({'method': 'peek_dice'}));
};

var revealDice = function(e) {
  e.preventDefault();
  websocket.send(JSON.stringify({'method': 'reveal_dice'}));
};
