"use strict";

const SQL_WASM_PATH = "js/sql-wasm.wasm";

const SQL_FROM_REGEX = /FROM\s+((?=['"])((["'])(?<g1>[^'"]+))|(?<g2>\w+))/mi;
const SQL_LIMIT_REGEX = /LIMIT\s+(\d+)(?:\s*,\s*(\d+))?/mi;
const SQL_SELECT_REGEX = /SELECT\s+[^;]+\s+FROM\s+/mi;

let db = null;
let loadedTableNames = [];
const errorBox = $("#error");
const infoBox = $("#info");

// Pagination State
let currentDataMode = null; // 'sql' or 'js'
let currentSqlBase = null;  // For SQL mode
let currentJsData = [];     // For JS mode
let currentPage = 0;
const PAGE_SIZE = 30;

const selectFormatter = function (item) {
    const index = item.text.indexOf("(");
    if (index > -1) {
        const name = item.text.substring(0, index);
        const tableName = item.text.substring(index - 1);
        return $(`<span>${name}<span style="color:#ccc">${tableName}</span></span>`);
    } else {
        return item.text;
    }
};

function setPage(el, next) {
    if (next) {
        currentPage++;
    } else {
        if (currentPage > 0) currentPage--;
    }
    renderCurrentPage();
}

function renderCurrentPage() {
    $("#bottom-bar").removeClass("d-none");
    
    let totalPages = 0;
    if (currentDataMode === 'sql') {
        const countQuery = currentSqlBase.replace(/SELECT\s+.*?\s+FROM/si, "SELECT COUNT(*) as count FROM");
        const sel = db.prepare(countQuery);
        if (sel.step()) {
            const count = sel.getAsObject().count;
            totalPages = Math.ceil(count / PAGE_SIZE);
        }
        sel.free();

        const paginatedQuery = `${currentSqlBase} ORDER BY t.month DESC LIMIT ${PAGE_SIZE} OFFSET ${currentPage * PAGE_SIZE}`;
        renderQuery(paginatedQuery);
    } else if (currentDataMode === 'js') {
        totalPages = Math.ceil(currentJsData.length / PAGE_SIZE);
        const start = currentPage * PAGE_SIZE;
        const end = start + PAGE_SIZE;
        const pageData = currentJsData.slice(start, end);
        renderTableFromArray(pageData);
    }

    $("#pager").text(`Page ${currentPage + 1} / ${totalPages || 1}`);
    $("#page-prev").prop("disabled", currentPage === 0);
    $("#page-next").prop("disabled", (currentPage + 1) >= totalPages);
}

function renderTableFromArray(data) {
    const dataBox = $("#data");
    const thead = dataBox.find("thead").find("tr");
    const tbody = dataBox.find("tbody");

    thead.empty();
    tbody.empty();
    errorBox.hide();
    infoBox.hide();
    dataBox.show();

    if (data.length === 0) {
        infoBox.text("No data found.").show();
        return;
    }

    const headers = ["Month", "Address", "Flat Type", "Floor", "Area (sqm)", "Price", "Lease Left"];
    headers.forEach(h => thead.append(`<th><span>${h}</span></th>`));

    data.forEach(row => {
        const tr = $('<tr>');
        const values = [
            row.month,
            row.address,
            row.flat_type,
            row.storey_range,
            row.floor_area_sqm,
            "$" + row.resale_price.toLocaleString(),
            Number(row.remaining_lease).toFixed(2) + " yrs"
        ];
        
        values.forEach(v => {
            let valStr = htmlEncode(String(v));
            tr.append(`<td><span title="${valStr}">${valStr}</span></td>`);
        });
        tbody.append(tr);
    });

    dataBox.editableTableWidget();
}

initialize();

function initialize() {
    let toggleFullScreen = function () {
        const container = $("#main-container");
        const resizerExpandIcon = $("#resizer-expand");
        const resizerCollapseIcon = $("#resizer-collapse");

        container.toggleClass("container container-fluid");
        resizerExpandIcon.toggle();
        resizerCollapseIcon.toggle();
    };
    $("#resizer").click(toggleFullScreen);

    if (typeof WebAssembly === "undefined") {
        $("#compat-error").toggleClass("d-none", false);
    }

    $(".no-propagate").on("click", function (el) {
        el.stopPropagation();
    });

    //Check url to load remote DB
    $.urlParam = function (name) {
        let results = new RegExp( `[\?&]${name}=([^&#]*)`).exec(window.location.href);
        if (results == null) {
            return null;
        } else {
            return results[1] || 0;
        }
    };
    const loadUrlDB = $.urlParam("url");
    if (loadUrlDB != null) {
        setIsLoading(true);
        const xhr = new XMLHttpRequest();
        xhr.open("GET", decodeURIComponent(loadUrlDB), true);
        xhr.responseType = "arraybuffer";
        xhr.onload = function (e) {
            loadDB(this.response);
        };
        xhr.onerror = function (e) {
            setIsLoading(false);
        };
        xhr.send();
    } else {
        // Load local transactions.db by default
        setIsLoading(true);
        const xhr = new XMLHttpRequest();
        xhr.open("GET", "transactions.db", true);
        xhr.responseType = "arraybuffer";
        xhr.onload = function (e) {
            if (this.status === 200) {
                loadDB(this.response);
            } else {
                setIsLoading(false);
            }
        };
        xhr.onerror = function (e) {
            setIsLoading(false);
        };
        xhr.send();
    }
}

function loadDB(arrayBuffer) {
    setIsLoading(true);

    initSqlJs({locateFile: file => SQL_WASM_PATH}).then(function (SQL) {
        try {
            db = new SQL.Database(new Uint8Array(arrayBuffer));
        } catch (ex) {
            setIsLoading(false);
            window.alert(ex);
            return;
        }

        $("#output-box").fadeIn();
        $("#loading-container").hide();
        $("#success-box").show();
        
        populateFilters();
        $("#filter-controls").fadeIn();
        plotAnalysis();

        setIsLoading(false);
    });
}

function populateFilters() {
    // Populate Towns
    try {
        const townsSelect = $("#filter-towns");
        if (townsSelect.hasClass("select2-hidden-accessible")) {
            townsSelect.select2('destroy');
        }
        townsSelect.empty();
        
        const townSel = db.prepare("SELECT name FROM towns ORDER BY name");
        while (townSel.step()) {
            const name = townSel.get()[0];
            townsSelect.append(new Option(name, name));
        }
        townSel.free();
        townsSelect.select2({ theme: "bootstrap-5", placeholder: "All Towns", width: '100%' });
    } catch (e) { 
        console.log("Towns table not found or empty", e); 
    }

    // Populate Flat Types
    try {
        const typesSelect = $("#filter-flat-types");
        const neighbourTypesSelect = $("#neighbour-flat-types");
        
        [typesSelect, neighbourTypesSelect].forEach(select => {
            if (select.hasClass("select2-hidden-accessible")) {
                select.select2('destroy');
            }
            select.empty();
        });

        const typeSel = db.prepare("SELECT name FROM flat_types ORDER BY name");
        while (typeSel.step()) {
            const name = typeSel.get()[0];
            typesSelect.append(new Option(name, name));
            neighbourTypesSelect.append(new Option(name, name));
        }
        typeSel.free();
        
        typesSelect.select2({ theme: "bootstrap-5", placeholder: "All Types", width: '100%' });
        neighbourTypesSelect.select2({ theme: "bootstrap-5", placeholder: "All Types", width: '100%' });
        
        // Set defaults for neighbourhood matching plot_neighbour.py
        neighbourTypesSelect.val(['3 ROOM', '4 ROOM', '5 ROOM']).trigger('change');

    } catch (e) { 
        console.log("Flat Types table not found or empty", e); 
    }

    // Populate Exclude Models
    try {
        const excludeSelect = $("#filter-exclude-models");
        if (excludeSelect.hasClass("select2-hidden-accessible")) {
            excludeSelect.select2('destroy');
        }
        excludeSelect.empty();

        const modelSel = db.prepare("SELECT name FROM flat_models ORDER BY name");
        while (modelSel.step()) {
            const name = modelSel.get()[0];
            excludeSelect.append(new Option(name, name));
        }
        modelSel.free();
        
        // Set defaults matching plot.py
        const defaults = ['Premium Apartment', 'Premium Apartment Loft', 'DBSS'];
        excludeSelect.val(defaults);
        
        excludeSelect.select2({ theme: "bootstrap-5", placeholder: "None", width: '100%' });
    } catch (e) { 
        console.log("Flat Models table not found or empty", e); 
    }

    // Populate Storey Ranges
    try {
        const storeySelects = [$("#filter-storey"), $("#neighbour-storey")];
        storeySelects.forEach(sel => {
            if (sel.hasClass("select2-hidden-accessible")) {
                sel.select2('destroy');
            }
            sel.empty();
        });

        const storeySel = db.prepare("SELECT DISTINCT storey_range FROM transactions ORDER BY storey_range");
        while (storeySel.step()) {
            const name = storeySel.get()[0];
            storeySelects.forEach(sel => sel.append(new Option(name, name)));
        }
        storeySel.free();
        
        storeySelects.forEach(sel => sel.select2({ theme: "bootstrap-5", placeholder: "All Storeys", width: '100%', allowClear: true }));
    } catch (e) {
        console.log("Error populating storey ranges", e);
    }
}

function getTableRowsCount(name) {
    const sel = db.prepare(`SELECT COUNT(*) AS count FROM '${name}'`);
    if (sel.step()) {
        const count = sel.getAsObject()["count"];
        sel.free();
        return count;
    } else {
        sel.free();
        return -1;
    }
}

function getQueryRowCount(query) {
    if (query === lastCachedQueryCount.select) {
        return lastCachedQueryCount.count;
    }

    let queryReplaced = query.replace(SQL_SELECT_REGEX, "SELECT COUNT(*) AS count FROM ");

    if (queryReplaced !== query) {
        queryReplaced = queryReplaced.replace(SQL_LIMIT_REGEX, "");
        const sel = db.prepare(queryReplaced);
        if (sel.step()) {
            const count = sel.getAsObject()["count"];
            sel.free();

            lastCachedQueryCount.select = query;
            lastCachedQueryCount.count = count;

            return count;
        } else {
            sel.free();
            return -1;
        }
    } else {
        return -1;
    }
}

function getTableColumnTypes(tableName) {
    let result = new Map();
    const sel = db.prepare(`PRAGMA table_info('${tableName}')`);

    while (sel.step()) {
        const obj = sel.getAsObject();
        let type = obj["type"];
        if (obj["notnull"] === 1) {
            type += " NOT NULL";
        }
        if (obj["pk"] === 1) {
            type += " PRIMARY KEY";
        }
        result.set(obj.name, type);
    }
    sel.free();

    return result;
}



function setIsLoading(isLoading) {
    const loading = $("#drop-loading");
    if (isLoading) {
        loading.toggleClass("d-none", false);
    } else {
        loading.toggleClass("d-none", true);
    }
}


function showError(msg) {
    $("#data").hide();
    errorBox.show();
    errorBox.text(msg);
}

function htmlEncode(value) {
    return $("<div/>").text(value).html();
}

function renderQuery(query) {
    const dataBox = $("#data");
    const thead = dataBox.find("thead").find("tr");
    const tbody = dataBox.find("tbody");

    thead.empty();
    tbody.empty();
    errorBox.hide();
    infoBox.hide();
    dataBox.show();

    let sel = null;
    try {
        sel = db.prepare(query);
    } catch (ex) {
        if (sel != null) {
            sel.free();
        }
        showError(ex);
        return;
    }

    let isEmptyTable = true;
    const columnNames = sel.getColumnNames();
    for (let i = 0; i < columnNames.length; i++) {
        thead.append(`<th><span>${columnNames[i]}</span></th>`);
    }

    while (sel.step()) {
        isEmptyTable = false;
        const tr = $('<tr>');
        const s = sel.get();
        for (let i = 0; i < s.length; i++) {
            let value = s[i];
            // Format remaining_lease if it's that column (index 6 based on plotAnalysis SQL)
            if (currentDataMode === 'sql' && i === 6 && typeof value === 'number') {
                value = value.toFixed(2);
            }
            let encoded = htmlEncode(String(value));
            tr.append(`<td><span title="${encoded}">${encoded}</span></td>`);
        }
        tbody.append(tr);
    }
    sel.free();

    if (isEmptyTable) {
        infoBox.text("No data for given select.");
        infoBox.show();
    }

    // Enable tooltips
    document.querySelectorAll('[data-bs-toggle="tooltip"]')
        .forEach(tooltipTriggerEl => new bootstrap.Tooltip(tooltipTriggerEl));

    dataBox.editableTableWidget();
}

function arrayToCsv(data) {
    return data.map(row =>
        row.map(String)  // convert every value to String
            .map(v => v.replaceAll('"', '""'))  // escape double quotes
            .map(v => `"${v}"`)  // quote it
            .join(',')  // comma-separated
    ).join('\r\n');  // rows starting on new lines
}

function exportCsvTableQuery(query) {
    let exportedRows = [];
    let sel = null;
    try {
        sel = db.prepare(query);
    } catch (ex) {
        if (sel != null) {
            sel.free();
        }
        showError(ex);
        setIsLoading(false);
        return null;
    }

    const columnNames = sel.getColumnNames();

    exportedRows.push(...[columnNames]);
    while (sel.step()) {
        const rows = sel.get();
        exportedRows.push(...[rows]);
    }
    sel.free();
    return exportedRows;
}

function exportCsvTable(tableName) {
    return exportCsvTableQuery(`SELECT * FROM '${tableName}'`);
}

function exportAllToCsv() {
    setIsLoading(true);
    const zip = new JSZip();
    for (const tableName of loadedTableNames) {
        const exportedRows = exportCsvTable(tableName);
        if (exportedRows != null) {
            zip.file(tableName + ".csv", arrayToCsv(exportedRows));
        } else {
            return;
        }
    }

    zip.generateAsync({type: "blob"})
        .then(function (content) {
            saveAs(content, "exported_all_db.zip");
        });
    setIsLoading(false);
}

function exportSelectedTableToCsv() {
    const tableName = $("#tables").val();
    setIsLoading(true);

    const exportedRows = exportCsvTable(tableName);
    if (exportedRows != null) {
        const blob = new Blob([arrayToCsv(exportedRows)], {type: "text/plain;charset=utf-8"});
        saveAs(blob, "exported_" + tableName.toLowerCase() + "_db.csv");
    }

    setIsLoading(false);
}

function exportQueryTableToCsv() {
    setIsLoading(true);

    const query = editor.getValue();
    const exportedRows = exportCsvTableQuery(query);
    if (exportedRows != null) {
        const blob = new Blob([arrayToCsv(exportedRows)], {type: "text/plain;charset=utf-8"});
        saveAs(blob, "exported_" + getTableNameFromQuery(query).toLowerCase() + "_db.csv");
    }

    setIsLoading(false);
}

function plotAnalysis() {
    if (!db) {
        showError("Please load a database first.");
        return;
    }

    $("#data").hide();
    $("#error").hide();
    $("#info").hide();
    $("#plot-container").show();

    const selectedTowns = $("#filter-towns").val(); // Array of strings or null
    const selectedTypes = $("#filter-flat-types").val(); // Array of strings or null
    const flatModelsExclude = $("#filter-exclude-models").val(); // Array of strings or null
    const monthsAgo = $("#filter-months").val() || 60;
    const selectedStorey = $("#filter-storey").val(); // Array of strings or null

    let query = `
        SELECT 
            CAST(t.remaining_lease AS INTEGER) as remaining_lease_int,
            (t.resale_price / (t.floor_area_sqm * 10.7639)) AS price_per_sqft
        FROM transactions t
        JOIN towns tw ON t.town_id = tw.id
        JOIN flat_types ft ON t.flat_type_id = ft.id
        JOIN flat_models fm ON t.flat_model_id = fm.id
        WHERE t.month >= date('now', '-${monthsAgo} months')
    `;

    if (selectedTowns && selectedTowns.length > 0) {
        const townList = selectedTowns.map(t => `'${t}'`).join(",");
        query += ` AND tw.name IN (${townList})`;
    }

    if (selectedTypes && selectedTypes.length > 0) {
        const typeList = selectedTypes.map(t => `'${t}'`).join(",");
        query += ` AND ft.name IN (${typeList})`;
    }

    if (flatModelsExclude && flatModelsExclude.length > 0) {
        const excludeList = flatModelsExclude.map(m => `'${m}'`).join(",");
        query += ` AND fm.name NOT IN (${excludeList})`;
    }

    if (selectedStorey && selectedStorey.length > 0) {
        const storeyList = selectedStorey.map(s => `'${s}'`).join(",");
        query += ` AND t.storey_range IN (${storeyList})`;
    }

    query += ` ORDER BY remaining_lease_int DESC`;

    let sel = null;
    try {
        sel = db.prepare(query);
    } catch (ex) {
        if (sel != null) sel.free();
        showError("Error executing query: " + ex + ". Ensure transactions.db is loaded.");
        $("#plot-container").hide();
        return;
    }

    const xData = [];
    const yData = [];

    while (sel.step()) {
        const row = sel.get(); // [remaining_lease_int, price_per_sqft]
        xData.push(row[0]);
        yData.push(row[1]);
    }
    sel.free();

    if (xData.length === 0) {
        $("#info").text("No data found for analysis.").show();
        $("#plot-container").hide();
        return;
    }

    const data = [{
        x: xData,
        y: yData,
        type: 'box',
        name: 'Price Distribution'
    }];

    // Generate dynamic title matching plot.py
    const townTitle = (selectedTowns && selectedTowns.length > 0) ? selectedTowns.join(", ") : 'ALL TOWNS';
    const flatTypeTitle = (selectedTypes && selectedTypes.length > 0) ? selectedTypes.join(", ") : 'ALL FLATS';
    const storeyTitle = (selectedStorey && selectedStorey.length > 0) ? `(Storey: ${selectedStorey.join(", ")})` : '(All Storeys)';
    const excludeTitle = (flatModelsExclude && flatModelsExclude.length > 0) ? `excluding ${flatModelsExclude.join(", ")}` : '';
    
    // Calculate ISO Week (approximate but matching standard JS week calculation)
    const now = new Date();
    const d = new Date(Date.UTC(now.getFullYear(), now.getMonth(), now.getDate()));
    const dayNum = d.getUTCDay() || 7;
    d.setUTCDate(d.getUTCDate() + 4 - dayNum);
    const yearStart = new Date(Date.UTC(d.getUTCFullYear(),0,1));
    const weekNum = Math.ceil((((d - yearStart) / 86400000) + 1) / 7);
    const year = d.getUTCFullYear();

    const layout = {
        title: {
            text: `PSF vs Remaining Lease for ${flatTypeTitle} in ${townTitle}<br><span style="font-size: 0.8em; color: gray;">${storeyTitle} ${excludeTitle}<br>(Last ${monthsAgo} months, Week ${weekNum} ${year})</span>`,
            font: { size: 18 }
        },
        xaxis: {
            title: 'Remaining Lease (Years)',
            type: 'linear',
            dtick: 1,
            autorange: 'reversed',
            showgrid: true,
            gridcolor: '#e2e2e2'
        },
        yaxis: {
            title: 'Price Per Square Foot (SGD)',
            showgrid: true,
            gridcolor: '#e2e2e2'
        },
        plot_bgcolor: 'white',
        paper_bgcolor: 'white',
        autosize: true
    };

    const config = { responsive: true };
    Plotly.newPlot('plot-container', data, layout, config);

    // Setup Table for Trends (SQL Mode)
    // We construct a query that fetches user-friendly columns
    let tableQuery = `
        SELECT 
            t.month,
            (b.address) AS full_address,
            ft.name AS flat_type,
            t.storey_range,
            t.floor_area_sqm,
            t.resale_price,
            t.remaining_lease
        FROM transactions t
        JOIN blocks b ON t.block_id = b.id
        JOIN towns tw ON t.town_id = tw.id
        JOIN flat_types ft ON t.flat_type_id = ft.id
        JOIN flat_models fm ON t.flat_model_id = fm.id
        WHERE t.month >= date('now', '-${monthsAgo} months')
    `;

    if (selectedTowns && selectedTowns.length > 0) {
        const townList = selectedTowns.map(t => `'${t}'`).join(",");
        tableQuery += ` AND tw.name IN (${townList})`;
    }

    if (selectedTypes && selectedTypes.length > 0) {
        const typeList = selectedTypes.map(t => `'${t}'`).join(",");
        tableQuery += ` AND ft.name IN (${typeList})`;
    }

    if (flatModelsExclude && flatModelsExclude.length > 0) {
        const excludeList = flatModelsExclude.map(m => `'${m}'`).join(",");
        tableQuery += ` AND fm.name NOT IN (${excludeList})`;
    }

    if (selectedStorey && selectedStorey.length > 0) {
        const storeyList = selectedStorey.map(s => `'${s}'`).join(",");
        tableQuery += ` AND t.storey_range IN (${storeyList})`;
    }

    currentDataMode = 'sql';
    currentSqlBase = tableQuery;
    currentPage = 0;
    renderCurrentPage();
}

async function plotNeighbourhood() {
    if (!db) {
        showError("Please load a database first.");
        return;
    }

    const targetAddr = $("#target-address").val();
    const radiusM = parseFloat($("#target-radius").val()) || 1000;
    const monthsAgo = $("#neighbour-months").val() || 24;
    const flatTypes = $("#neighbour-flat-types").val();
    const selectedStorey = $("#neighbour-storey").val();

    if (!targetAddr) {
        showError("Please enter a target address.");
        return;
    }

    $("#data").hide();
    $("#error").hide();
    $("#info").hide();
    setIsLoading(true);

    try {
        // 1. Geocode via OneMap API
        const response = await fetch(`https://www.onemap.gov.sg/api/common/elastic/search?searchVal=${encodeURIComponent(targetAddr)}&returnGeom=Y&getAddrDetails=Y`);
        const result = await response.json();
        
        if (result.found === 0) {
            setIsLoading(false);
            showError("Address not found on OneMap.");
            return;
        }

        const xRef = parseFloat(result.results[0].X);
        const yRef = parseFloat(result.results[0].Y);
        const foundAddr = result.results[0].ADDRESS;

        // 2. Query bounding box from DB
        let query = `
            SELECT 
                t.month,
                b.address,
                t.storey_range,
                t.floor_area_sqm,
                t.resale_price,
                t.remaining_lease,
                (t.resale_price / (t.floor_area_sqm * 10.7639)) AS price_per_sqft,
                b.x, b.y,
                ft.name AS flat_type
            FROM transactions t
            JOIN blocks b ON t.block_id = b.id
            JOIN flat_types ft ON t.flat_type_id = ft.id
            WHERE b.x BETWEEN ${xRef - radiusM} AND ${xRef + radiusM}
              AND b.y BETWEEN ${yRef - radiusM} AND ${yRef + radiusM}
              AND t.month >= date('now', '-${monthsAgo} months')
        `;

        if (flatTypes && flatTypes.length > 0) {
            const typeList = flatTypes.map(t => `'${t}'`).join(",");
            query += ` AND ft.name IN (${typeList})`;
        }

        if (selectedStorey && selectedStorey.length > 0) {
            const storeyList = selectedStorey.map(s => `'${s}'`).join(",");
            query += ` AND t.storey_range IN (${storeyList})`;
        }

        const sel = db.prepare(query);
        const xData = [];
        const yData = [];
        const tableData = [];

        while (sel.step()) {
            const row = sel.getAsObject();
            // 3. Precise distance filter (Euclidean)
            const dist = Math.sqrt(Math.pow(row.x - xRef, 2) + Math.pow(row.y - yRef, 2));
            if (dist <= radiusM) {
                xData.push(Math.floor(row.remaining_lease));
                yData.push(row.price_per_sqft);
                tableData.push(row);
            }
        }
        sel.free();

        if (xData.length === 0) {
            setIsLoading(false);
            $("#info").text(`No transactions found within ${radiusM}m of ${foundAddr} in the last ${monthsAgo} months.`).show();
            $("#plot-container").hide();
            $("#bottom-bar").addClass("d-none"); // Hide pager if no data
            return;
        }

        // Setup Table for Neighbourhood (JS Mode)
        // Sort by month descending
        tableData.sort((a, b) => {
            if (a.month < b.month) return 1;
            if (a.month > b.month) return -1;
            return 0;
        });

        currentDataMode = 'js';
        currentJsData = tableData;
        currentPage = 0;
        renderCurrentPage();

        // 4. Plot
        $("#plot-container").show();
        const data = [{
            x: xData,
            y: yData,
            type: 'box',
            name: 'Local PSF Distribution'
        }];

        const now = new Date();
        const d = new Date(Date.UTC(now.getFullYear(), now.getMonth(), now.getDate()));
        const dayNum = d.getUTCDay() || 7;
        d.setUTCDate(d.getUTCDate() + 4 - dayNum);
        const yearStart = new Date(Date.UTC(d.getUTCFullYear(),0,1));
        const weekNum = Math.ceil((((d - yearStart) / 86400000) + 1) / 7);

        const storeyTitle = (selectedStorey && selectedStorey.length > 0) ? `(Storey: ${selectedStorey.join(", ")})` : '(All Storeys)';

        const layout = {
            title: {
                text: `PSF vs Remaining Lease within ${radiusM}m of ${foundAddr}<br><span style="font-size: 0.8em; color: gray;">${storeyTitle} (${flatTypes ? flatTypes.join(", ") : 'All Types'}) - Last ${monthsAgo} months (Week ${weekNum} ${now.getFullYear()})</span>`,
                font: { size: 16 }
            },
            xaxis: {
                title: 'Remaining Lease (Years)',
                type: 'linear',
                dtick: 1,
                autorange: 'reversed',
                showgrid: true,
                gridcolor: '#e2e2e2'
            },
            yaxis: {
                title: 'Price Per Square Foot (SGD)',
                showgrid: true,
                gridcolor: '#e2e2e2'
            },
            plot_bgcolor: 'white',
            paper_bgcolor: 'white',
            autosize: true
        };

        const config = { responsive: true };
        Plotly.newPlot('plot-container', data, layout, config);
        setIsLoading(false);

    } catch (err) {
        setIsLoading(false);
        showError("Error: " + err.message);
    }
}
