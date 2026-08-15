console.log("called");

const session_id = "123s";
const token = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJjbGllbnRfaWQiOiIxIiwidXNlcl9pZCI6IjEiLCJleHAiOjE5MDI5MTkwOTl9.3vFc7ux6_4H-E_bzInaLgbgs9RRd-XC2vHE3LMZu71U";
const customHeaders = {
  "Authorization": `Bearer ${token}`,
};
// socket code start
// ?token=${encodeURIComponent(token)}
let backEnd = `${location.protocol === "https:" ? "wss" : "ws"}://${location.host}/ws/${session_id}?token=${encodeURIComponent(token)}`;
console.log("Connecting to WebSocket at:", backEnd);

var ws = new WebSocket(backEnd);

ws.addEventListener("open", (event) => {
  console.log("WebSocket connected.");
  ws.send(JSON.stringify({ msg: "ping" }));
});

ws.addEventListener("message", (event) => {
  console.log("Message received:", event.data);
  let data = JSON.parse(event.data);
  appendWebSocketMessage(data);
});

ws.addEventListener("error", (event) => {
  console.error("WebSocket error:", event);
});

ws.onclose = (event) => {
  console.warn(`WebSocket closed. Code: ${event.code}, Reason: ${event.reason}`);
};


//ws.onmessage = function(event) {
//    let data = JSON.parse(event.data);
//    appendWebSocketMessage(data);
//};
// socket code end

var uid = "1";
const msgerForm = get(".msger-inputarea");
const msgerInput = get(".msger-input");
const msgerChat = get(".msger-chat");

const feedbackForm = get(".feedback-form");
const feedbackFormContent = get(".feedback-content");

// Icons made by Freepik from www.flaticon.com
const BOT_IMG = "./static/images/bot.png";
const PERSON_IMG = "./static/images/user.png";
const BOT_NAME = "ChatBot";
const PERSON_NAME = "You";
const Config = {
  BOT_IMG_CLASS : "bot-image",
  PERSON_IMG_CLASS: "user-image"
}

msgerForm.addEventListener("submit", (event) => {
  event.preventDefault();
  const msgText = msgerInput.value;

  if (!msgText) return;
  let data = {
    query: msgText,
  };
//  sendQuery(msgText)
    sendQuery(session_id, msgText, customHeaders)
    .then((response) => {
      let input = document.getElementById("textInput");
      if (input) {
        input.value = "";
      }
      console.log(`query save response: ${response.query_id}`);
      appendQueryBlock(response.query_id, msgText);
      appendQueryResponseBlock(response.query_id);
      data.query_id = response.query_id;
//      ws.send(JSON.stringify(data));
      getQueryResponse(session_id,response.query_id, customHeaders);
    })
    .catch(() => {
      console.log("error");
    });
  ans = [];

  // appendMessage(PERSON_NAME, PERSON_IMG, "right", msgText);
  // botResponse(msgText);
});

// appends query block asked by user
function appendQueryBlock(query_id, query) {
  msgHTML = `
  <div class="msg right-msg">
          <img src="../static/images/user1.png" class="user-image" alt="">
    <div class="msg-bubble">
      <div class="msg-info">
        <div class="msg-info-name">${PERSON_NAME}</div>
        <div class="msg-info-time">${formatDate(new Date())}</div>
      </div>

      <div class="msg-text">${query}</div>
    </div>
  </div>
  `;

  msgerChat.insertAdjacentHTML("beforeend", msgHTML);
  msgerChat.scrollTop += 500;
}

// appends query response block,
// websocket will write the generated
// answer in this block
function appendQueryResponseBlock(query_id) {
  msgHTML = `
      <div class="msg left-msg">
        <img src="../static/images/bot.png" class="bot-image" alt="">
<div class="msg-bubble">
<div class="msg-info">
   <div class="msg-info-name">${BOT_NAME}</div>
   <div class="msg-info-time">${formatDate(new Date())}</div>

      </div>
      <div class="msg-text-response" id=${query_id}></div>
      <div id="feedback-${query_id}"></div>
   </div>
</div>

`;

  msgerChat.insertAdjacentHTML("beforeend", msgHTML);
  msgerChat.scrollTop += 500;
}

function appendFeedback(query_id) {
  feedBackHTML = `<div class="feedback-form-container">
      <form class="feedback-form">
       <div>
            Rating :
            <i id="star-1" class="fa fa-regular fa-star"></i>
            <i id="star-2" class="fa fa-regular fa-star"></i>
            <i id="star-3" class="fa fa-regular fa-star"></i>
            <i id="star-4" class="fa fa-regular fa-star"></i>
            <i id="star-5" class="fa fa-regular fa-star"></i>
         </div>
         <div class="feedback-text">
            <span>FeedBack: </span>
            <textarea class="feedback-content" id=feedbackContent-${query_id}></textarea>
         </div>
         <button type="submit" class="btn btn-primary">Submit</button>
      </form>
</div>`;

  let div = document.getElementById(`feedback-${query_id}`);
  if (div) {
    div.innerHTML = feedBackHTML;
  }
}

let messageBuffer = {};

function appendWebSocketMessage(data) {
    console.log(`Appending websocket message: ${JSON.stringify(data)}`);
    let topic = data.topic;
    let message = data.data;
    let query_id = data.query_id;

    if (topic === "model_stream") {
        if (!messageBuffer[query_id]) {
            messageBuffer[query_id] = "";
        }
        messageBuffer[query_id] += message;  // Buffer incoming messages

        let div = document.getElementById(query_id);
        console.log(`got the div: ${div}`);
        if (div) {
            div.textContent += messageBuffer[query_id];  // Append complete text
            div.scrollIntoView({ behavior: "auto" });
        }
    } else {
        appendFeedback(query_id);
        let lastElement = document.getElementById(query_id);
        console.log(`lastElement ${lastElement}`)
        if (lastElement) {
            lastElement.scrollIntoView({ behavior: "auto" });
        }
    }
    messageBuffer = {};
}

function append(ans) {
  if (ans && ans.length) {
    let div = document.getElementsByClassName("msg-text-response");
    console.log("got the div " + div);
    if (div[0]) {
      div[0].textContent += ans[0];
      div[0].textContent += " ";
    }
    ans.shift();
  }
}

msgerChat.addEventListener("click", (event) => {
  if (
    event.target.classList.contains("fa-star") ||
    event.target.tagName == "path"
  ) {
    let star;
    if (event.target.tagName == "path") {
      star = event.target.parentNode;
    } else {
      star = event.target;
    }
    const stars = Array.from(star.parentNode.children);
    const index = stars.indexOf(star);

    stars.forEach((s, i) => {
      if (i <= index) {
        s.classList.add("filled");
      } else {
        s.classList.remove("filled");
      }
    });
  }
});

msgerChat.addEventListener("submit", (event) => {
  event.preventDefault();
  if (event.target.matches(".feedback-form")) {
    const feedbackForm = event.target;
    event.preventDefault();
    const feedbackContent =
      feedbackForm.querySelector(".feedback-content").value;
    const rating = feedbackForm.querySelectorAll(".fa-star.filled").length;

    let feedBackId = feedbackForm.querySelector(".feedback-content").id
    let query_id = feedBackId.split("-")[1]

    // Sending the feedback through websocket
    const feedbackPayload = {
      query_id: query_id,
      is_answer_satisfactory: rating,
      feedback: feedbackContent
    };
    // Send feedback via WebSocket
    if (ws.readyState === WebSocket.OPEN) {
      ws.send(JSON.stringify(feedbackPayload));
      feedbackForm.closest(".feedback-form-container").style.display = "none";
      alert("Feedback submitted successfully.");
    } else {
      alert("Feedback submission failed.");
    }
  }
});

//    console.log(`query ID: ${query_id}`)
//    $.post("/feedback", {
//      query_id: query_id,
//      rating: rating,
//      comment: feedbackContent,
//    }).done(function (response) {
//      if (response === "success") {
// feedbackForm.addEventListener("submit", event => {
//   event.preventDefault();

//   console.log(event);
//   console.log(feedbackFormContent.value);
//   debugger
// });

function appendMessage(name, img, side, text) {
  let isRight = side == "right";
  let msgHTML = "";

  if (isRight) {
    msgHTML = `
<div class="msg ${side}-msg">
        <img src="../static/images/user1.png" class="user-image" alt="">
  <div class="msg-bubble">
    <div class="msg-info">
      <div class="msg-info-name">${name}</div>
      <div class="msg-info-time">${formatDate(new Date())}</div>
    </div>

    <div class="msg-text">${text}</div>
  </div>
</div>
`;
  } else {
    msgHTML = `
      <div class="msg ${side}-msg">
        <img src="../static/images/bot.png" class="bot-image" alt="">
<div class="msg-bubble">
<div class="msg-info">
   <div class="msg-info-name">${name}</div>
   <div class="msg-info-time">${formatDate(new Date())}</div>

      </div>
      <div class="msg-text-response"></div>
      <div class="feedback-form-container">
      <form class="feedback-form">
       <div>
            Rating :
            <i id="star-1" class="fa fa-regular fa-star"></i>
            <i id="star-2" class="fa fa-regular fa-star"></i>
            <i id="star-3" class="fa fa-regular fa-star"></i>
            <i id="star-4" class="fa fa-regular fa-star"></i>
            <i id="star-5" class="fa fa-regular fa-star"></i>
         </div>
         <div class="feedback-text">
            <span>FeedBack: </span>
            <textarea class="feedback-content"></textarea>
         </div>
         <button type="submit" class="btn btn-primary">Submit</button>
      </form>
</div>
   </div>
</div>

`;
  }
  msgerChat.insertAdjacentHTML("beforeend", msgHTML);
  msgerChat.scrollTop += 500;
}

document.addEventListener("DOMContentLoaded", function () {
  document.addEventListener("keypress", function (event) {
    if (event.key === "Enter" && !event.shiftKey) {
      const activeElement = document.activeElement;
      if (activeElement.classList.contains("feedback-content")) {
        event.preventDefault(); // Prevent default Enter behavior (new line)
        const feedbackForm = activeElement.closest(".feedback-form");
        if (feedbackForm) {
          const submitButton = feedbackForm.querySelector(
            'button[type="submit"]'
          );
          if (submitButton) {
            submitButton.click();
          }
        }
      }
    }
  });
});

function botResponse(rawText) {
  appendMessage(BOT_NAME, BOT_IMG, "left", "");

  // Bot Response
  $.get("/get_response", { query: rawText }).done(function (data) {
    const msgText = data.resp;
    uid = data.id;
    console.log(uid);
    // appendMessage(BOT_NAME, BOT_IMG, "left", '');
  });
}

// Utils
function get(selector, root = document) {
  return root.querySelector(selector);
}

function formatDate(date) {
  const h = "0" + date.getHours();
  const m = "0" + date.getMinutes();

  return `${h.slice(-2)}:${m.slice(-2)}`;
}

function appendMessages(info, index, list) {
  query_id = info.id
  query = info.question
  response = info.answer
  createdDate = info.created_date

  dateObject = new Date(createdDate)

  botMessageHTML = generateMessageBlock(
    "left", BOT_NAME, query_id, BOT_IMG, response, dateObject, Config.BOT_IMG_CLASS);

  userMessageHTML = generateMessageBlock(
    "right", PERSON_NAME, query_id, PERSON_IMG, query, dateObject, Config.PERSON_IMG_CLASS);

  let divElement = document.getElementsByClassName("msg-qa-ans")
  if (divElement) {
    // divElement[0].insertAdjacentElement("beforeend", userMessageHTML)
    // divElement[0].insertAdjacentElement("beforeend", botMessageHTML)
    divElement[0].innerHTML += userMessageHTML
    divElement[0].innerHTML += botMessageHTML
  }


}

// appends home screen conversation
function appendHomeConversation() {
  getHomeData()
    .then((response) => {
      let conversations = response;
      let topMessage = "Hi, welcome to ChatBot! Go ahead and send me a message. 😄"
      let divElement = document.getElementsByClassName("msg-qa-ans")
      if (divElement) {
        divElement[0].innerHTML += generateMessageBlock(
          "left", BOT_NAME, "", BOT_IMG, topMessage, null, Config.BOT_IMG_CLASS);
      }

      conversations.forEach(appendMessages)

      let lastElementIndex = conversations[conversations.length-1].id
      let lastElement = document.getElementById(lastElementIndex)
      if (lastElement) {
        lastElement.scrollIntoView({"behavior": "auto"})
      }
      // window.scrollTo(0, document.body.scrollHeight)
    })
    .catch((err) => {
      console.log(`error: ${err}`);
    });
}

