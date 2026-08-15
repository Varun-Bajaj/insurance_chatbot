// gets home page data,
// includes question/answer
function getHomeData() {
  return $.get("/bot/home", {}).done(function (response) {
    return response;
  });
}

function sendQuery(session_id, query, headers) {
    return fetch("/api/bot/query/save", {
        method: "POST",
        headers: {
            "Content-Type": "application/json",
            ...headers // Include custom headers
        },
        body: JSON.stringify({ session_id: session_id, query: query })
    })
    .then(response => {
        if (!response.ok) {
            throw new Error(`HTTP error! Status: ${response.status}`);
        }
        return response.json();
    })
    .then(data => {
        console.log("Query saved in BE:", data);
        return data; // Return data to be used in `.then()`
    })
    .catch(error => {
        console.error("Error saving query:", error);
        throw error; // Ensure error propagates
    });
}

function getQueryResponse(session_id, query_id, headers) {
    let url = `/api/bot/query/response?session_id=${encodeURIComponent(session_id)}&query_id=${encodeURIComponent(query_id)}`;

    return fetch(url, {
        method: "GET",
        headers: {
            "Content-Type": "application/json",
            ...headers
        }
    })
    .then(response => {
        if (!response.ok) {
            throw new Error(`HTTP error! Status: ${response.status}`);
        }
        return response.json();
    })
    .then(data => {
        console.log("Response from chatbot:", data);
        return data; // Return response data
    })
    .catch(error => {
        console.error("Error getting query response:", error);
        throw error;
    });
}

// sends query to backend and will ceate a div element
//function sendQuery(query) {
//  return $.post("/api/bot/query/save", query).done(function (response) {
//    console.log("query saved in BE " + response);
//    return response;
//  });
//}

// gets query response from backend
//function getQueryResponse(query_id) {
//  return $.get("/api/bot/query/response", { query_id: query_id}).done(function (
//    response
//  ) {
//    return response;
//  });
//}
