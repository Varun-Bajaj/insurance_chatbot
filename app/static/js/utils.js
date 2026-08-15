// generates message block
function generateMessageBlock(position, sendersName, query_id, imageName, query, dateObject, imageClass) {

    dateTimeString = "";
    if (dateObject) {
        dateTimeString = formatDate(dateObject)
    }

    msgHTML = `
    <div class="msg ${position}-msg">
      <img src="${imageName}" class="${imageClass}" alt="">
<div class="msg-bubble">
<div class="msg-info">
 <div class="msg-info-name">${sendersName}</div>
 <div class="msg-info-time">${dateTimeString}</div>
 
    </div>
    <div class="msg-text-response" id=${query_id}></div>
    <div id="feedback-${query_id}">${query}</div>
 </div>
</div>
`;

    return msgHTML

}
