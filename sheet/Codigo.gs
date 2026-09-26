/**
 * The spreadsheet's half of the bridge.
 *
 * It lives inside the spreadsheet, so there is no Google Cloud project,
 * no consent screen and no key to rotate. The server posts one action
 * per call and this carries it out.
 *
 * Deploy: Extensions -> Apps Script, paste this, set SHEET_ID and
 * SHARED_WORD, then Deploy -> New deployment -> Web app, running as
 * yourself, access "Anyone with the link". Copy the URL it gives back.
 */

/** The spreadsheet, by the long code in its own address. */
var SHEET_ID = 'put-the-id-here';

/** A word only the server knows, so a stranger with the URL does nothing. */
var SHARED_WORD = 'change-me';

/** Nobody reads a million rows on purpose. */
var MOST_ROWS = 5000;

function doPost(request) {
  try {
    var asked = JSON.parse(request.postData.contents);
    if (asked.word !== SHARED_WORD) {
      return reply({ok: false, why: 'wrong word'});
    }
    return reply(carryOut(asked));
  } catch (failure) {
    return reply({ok: false, why: String(failure)});
  }
}

function doGet() {
  return reply({ok: true, tabs: tabNames()});
}

/** One action, by name. An unknown name is said so, never guessed. */
function carryOut(asked) {
  if (asked.action === 'tabs') { return {ok: true, tabs: tabNames()}; }
  if (asked.action === 'read') { return readRows(asked); }
  if (asked.action === 'find') { return findRows(asked); }
  if (asked.action === 'append') { return appendRow(asked); }
  if (asked.action === 'update') { return updateRow(asked); }
  return {ok: false, why: 'unknown action ' + asked.action};
}

function tabNames() {
  return SpreadsheetApp.openById(SHEET_ID).getSheets().map(function (s) {
    return s.getName();
  });
}

/** Every row of a tab, as objects keyed by the header. */
function readRows(asked) {
  var table = tableOf(asked.tab);
  if (!table.ok) { return table; }
  var limit = Math.min(asked.limit || MOST_ROWS, MOST_ROWS);
  return {
    ok: true,
    columns: table.columns,
    rows: table.rows.slice(0, limit),
    total: table.rows.length
  };
}

/** The rows whose named column holds a given value. */
function findRows(asked) {
  var table = tableOf(asked.tab);
  if (!table.ok) { return table; }
  if (table.columns.indexOf(asked.column) < 0) {
    return {ok: false, why: 'no column called ' + asked.column,
            columns: table.columns};
  }
  var wanted = String(asked.value).trim().toLowerCase();
  var found = table.rows.filter(function (row) {
    var held = String(row[asked.column] === undefined ? '' : row[asked.column]);
    return asked.exact
      ? held.trim().toLowerCase() === wanted
      : held.toLowerCase().indexOf(wanted) >= 0;
  });
  return {ok: true, columns: table.columns, rows: found, total: found.length};
}

/** Add one row at the bottom, in the order the header sets. */
function appendRow(asked) {
  var table = tableOf(asked.tab);
  if (!table.ok) { return table; }
  var line = table.columns.map(function (name) {
    return asked.row[name] === undefined ? '' : asked.row[name];
  });
  var tab = SpreadsheetApp.openById(SHEET_ID).getSheetByName(asked.tab);
  tab.appendRow(line);
  return {ok: true, at: tab.getLastRow(), written: 1};
}

/**
 * Change named cells of one row, found by another column's value.
 *
 * It refuses when more than one row matches. Changing several rows on a
 * loose match is how a spreadsheet gets quietly ruined.
 */
function updateRow(asked) {
  var table = tableOf(asked.tab);
  if (!table.ok) { return table; }
  var at = [];
  for (var i = 0; i < table.rows.length; i++) {
    if (String(table.rows[i][asked.column]) === String(asked.value)) {
      at.push(i + 2);
    }
  }
  if (at.length === 0) {
    return {ok: false, why: 'no row where ' + asked.column + ' is ' + asked.value};
  }
  if (at.length > 1) {
    return {ok: false, why: 'that matches ' + at.length + ' rows, so nothing was changed'};
  }
  var tab = SpreadsheetApp.openById(SHEET_ID).getSheetByName(asked.tab);
  var changed = [];
  for (var name in asked.changes) {
    var col = table.columns.indexOf(name);
    if (col < 0) { return {ok: false, why: 'no column called ' + name}; }
    tab.getRange(at[0], col + 1).setValue(asked.changes[name]);
    changed.push(name);
  }
  return {ok: true, at: at[0], changed: changed};
}

/** One tab as a header and a list of objects. */
function tableOf(name) {
  var tab = SpreadsheetApp.openById(SHEET_ID).getSheetByName(name);
  if (!tab) { return {ok: false, why: 'no tab called ' + name, tabs: tabNames()}; }
  var values = tab.getDataRange().getValues();
  if (!values.length) { return {ok: true, columns: [], rows: []}; }
  var columns = values[0].map(function (c) { return String(c); });
  var rows = [];
  for (var r = 1; r < values.length; r++) {
    var row = {};
    var empty = true;
    for (var c = 0; c < columns.length; c++) {
      var cell = values[r][c];
      row[columns[c]] = cell instanceof Date ? asDay(cell) : cell;
      if (String(cell).trim() !== '') { empty = false; }
    }
    if (!empty) { rows.push(row); }
  }
  return {ok: true, columns: columns, rows: rows};
}

/** A date as the day it is, with no clock and no time zone to argue over. */
function asDay(when) {
  return Utilities.formatDate(when, Session.getScriptTimeZone(), 'yyyy-MM-dd');
}

function reply(body) {
  return ContentService
    .createTextOutput(JSON.stringify(body))
    .setMimeType(ContentService.MimeType.JSON);
}
