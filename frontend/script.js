const startButton = document.getElementById('startButton');
const stopButton = document.getElementById('stopButton');
const statusDiv = document.getElementById('status');
const conversationLog = document.getElementById('conversationLog');

let mediaRecorder;      
let recordedChunks = [];
let audioBlob;          
let websocket;          
let audioContext;       
let audioQueue = [];    
let isPlaying = false;  
let sessionID = 'session_' + Date.now();

const WS_URL = `ws://localhost:8000/ws/${sessionID}`;
const RECONNECT_DELAY = 3000;

/**
 * Updates the status display text and applies corresponding CSS classes.
 * @param {string} message
 * @param {boolean} isError 
 */
function updateStatus(message, isError = false) {
    console.log("Status:", message);
    statusDiv.textContent = `Status: ${message}`;

    statusDiv.classList.remove('recording', 'processing', 'playing', 'error');
    const lowerMessage = message.toLowerCase();

    if (isError || lowerMessage.includes('error')) {
         statusDiv.classList.add('error');
    } else if (lowerMessage.includes('recording')) {
        statusDiv.classList.add('recording');
    } else if (lowerMessage.includes('processing') || lowerMessage.includes('transcribing') || lowerMessage.includes('thinking') || lowerMessage.includes('synthesizing')) {
        statusDiv.classList.add('processing');
    } else if (lowerMessage.includes('playing')) {
        statusDiv.classList.add('playing');
    }
}

/**
 * Adds a message entry (user or assistant) to the conversation log UI.
 * @param {string} speaker
 * @param {string} text
 */
function addLogEntry(speaker, text) {
    if (conversationLog) {
        console.log(`Adding log for ${speaker}. Full text received:`, text);
        const entry = document.createElement('p');
        const sanitizedText = text.replace(/</g, "&lt;").replace(/>/g, "&gt;");
        entry.innerHTML = `<strong>${speaker}:</strong> ${sanitizedText}`;
        conversationLog.appendChild(entry);
        conversationLog.scrollTo({ top: conversationLog.scrollHeight, behavior: 'smooth' });
    } else {
        console.warn("Conversation log element not found.");
    }
}

function connectWebSocket() {
    updateStatus('Connecting to server...');
    if (websocket && (websocket.readyState === WebSocket.OPEN || websocket.readyState === WebSocket.CONNECTING)) {
        console.log("WebSocket already open or connecting.");
        return;
    }

    websocket = new WebSocket(WS_URL);
    websocket.binaryType = "arraybuffer";

    websocket.onopen = () => {
        updateStatus('Connected. Ready.');
        startButton.disabled = false;
        stopButton.disabled = true;
        startButton.classList.remove('recording');
    };

    websocket.onmessage = async (event) => {
        if (event.data instanceof ArrayBuffer) {
            const audioData = event.data;
            if (audioData.byteLength > 0) {
                 console.log(`>>> Queuing audio chunk size: ${audioData.byteLength}`);
                audioQueue.push(audioData);
                if (!isPlaying) {
                    processAudioQueue();
                }
            } else {
                console.warn("Received empty audio chunk from server.");
            }
        } else if (typeof event.data === 'string') {
            const message = event.data;
            console.log("Received text:", message);
            if (message.startsWith('STATUS:')) {
                const statusText = message.substring(7).trim();
                if (!isPlaying) {
                     updateStatus(statusText);
                     if (statusText === 'Ready') {
                          console.log("Backend Ready & Frontend Not Playing: Enabling Start Button");
                          startButton.disabled = false;
                          stopButton.disabled = true;
                          startButton.classList.remove('recording');
                     } else {
                          startButton.disabled = true;
                          console.log(`Backend not Ready (${statusText}): Disabling Start Button`);
                     }
                } else {
                    console.log(`Backend status update while playing: ${statusText}`);
                }

            } else if (message.startsWith('ERROR:')) {
                updateStatus(`Server Error: ${message.substring(6).trim()}`, true);
                if (!isPlaying && (!mediaRecorder || mediaRecorder.state === 'inactive')) {
                    startButton.disabled = false;
                    stopButton.disabled = true;
                    startButton.classList.remove('recording');
                }
            } else if (message.startsWith('USER_TRANSCRIPT:')) {
                addLogEntry('You', message.substring(16).trim());
            } else if (message.startsWith('AI_RESPONSE:')) {
                addLogEntry('Assistant', message.substring(12).trim());
            } else {
                updateStatus(`Server message: ${message}`);
            }
        }
    };

    websocket.onerror = (error) => {
        console.error('WebSocket Error:', error);
        updateStatus('WebSocket error.', true);
        startButton.disabled = true;
        stopButton.disabled = true;
        startButton.classList.remove('recording');
    };

    websocket.onclose = (event) => {
        console.log('WebSocket Closed:', event.reason, event.code);
        mediaRecorder = null;
        startButton.disabled = true;
        stopButton.disabled = true;
        isPlaying = false;
        audioQueue = [];
        startButton.classList.remove('recording');
        if (event.code !== 1000 && event.code !== 1005) {
            updateStatus(`Disconnected. Retrying in ${RECONNECT_DELAY / 1000}s...`);
            setTimeout(connectWebSocket, RECONNECT_DELAY);
        } else {
             updateStatus('Disconnected.');
        }
    };
}

async function startRecording() {
    if (!navigator.mediaDevices || !navigator.mediaDevices.getUserMedia) {
         updateStatus('Error: MediaDevices API not supported.', true);
         return;
    }
    if (websocket?.readyState !== WebSocket.OPEN) {
         updateStatus('Error: WebSocket not connected.', true);
         return;
    }
    if (!audioContext) {
        try {
            audioContext = new (window.AudioContext || window.webkitAudioContext)();
            if (audioContext.state === 'suspended') { await audioContext.resume(); console.log("AudioContext resumed."); }
        } catch(e) {
            console.error("Failed to create/resume AudioContext", e);
            updateStatus("Error: Cannot initialize audio playback.", true);
            return;
        }
    } else if (audioContext.state === 'suspended') {
         try { await audioContext.resume(); console.log("AudioContext resumed."); }
         catch(e) { console.error("Failed to resume existing AudioContext", e); updateStatus("Error: Could not resume audio playback.", true); return; }
    }


    try {
        const stream = await navigator.mediaDevices.getUserMedia({ audio: true });

        const options = { mimeType: 'audio/webm;codecs=opus' };
         if (!MediaRecorder.isTypeSupported(options.mimeType)) {
             console.warn(`${options.mimeType} not supported, trying default.`);
             options.mimeType = 'audio/ogg;codecs=opus';
             if(!MediaRecorder.isTypeSupported(options.mimeType)){
                 console.warn(`${options.mimeType} also not supported, using browser default.`);
                 delete options.mimeType;
             }
        }

        mediaRecorder = new MediaRecorder(stream, options);
        recordedChunks = [];

        mediaRecorder.ondataavailable = (event) => {
            if (event.data.size > 0) { recordedChunks.push(event.data); }
        };

        mediaRecorder.onstop = () => {
            audioBlob = new Blob(recordedChunks, { type: options.mimeType || 'audio/webm' });
            console.log(`Created audio Blob size: ${audioBlob.size}, type: ${audioBlob.type}`);
            sendAudioData(audioBlob);
            stream.getTracks().forEach(track => track.stop());
            console.log("Microphone stream stopped.");
        };

        mediaRecorder.start();
        updateStatus('Recording...');
        startButton.classList.add('recording');
        startButton.disabled = true;
        stopButton.disabled = false;

    } catch (err) {
         console.error('Error accessing microphone:', err);
         updateStatus(`Error: ${err.message}`, true);
         startButton.disabled = false;
         stopButton.disabled = true;
         startButton.classList.remove('recording');
    }
}


function stopRecording() {
    if (mediaRecorder && mediaRecorder.state === 'recording') {
        mediaRecorder.stop();
        stopButton.disabled = true;
        startButton.classList.remove('recording');
        updateStatus('Stopping recording...');
    } else {
         console.warn("Stop recording called but recorder not active.");
         startButton.disabled = false;
         stopButton.disabled = true;
         startButton.classList.remove('recording');
    }
}

/**
 * Sends the complete audio recording (as a Blob) to the backend via WebSocket.
 * @param {Blob} blobToSend
 */
function sendAudioData(blobToSend) {
    if (websocket?.readyState === WebSocket.OPEN) {
        if (blobToSend && blobToSend.size > 0) {
            updateStatus("Sending audio data...");
            startButton.disabled = true;
            blobToSend.arrayBuffer().then((arrayBuffer) => {
                websocket.send(arrayBuffer);
                updateStatus("Audio sent. Waiting for response...");
                console.log(`Sent ArrayBuffer size: ${arrayBuffer.byteLength}`);
                audioQueue = [];
                isPlaying = false;
            }).catch(error => {
                console.error("Error converting Blob to ArrayBuffer:", error);
                updateStatus("Error preparing audio data.", true);
                startButton.disabled = false;
                stopButton.disabled = true;
                startButton.classList.remove('recording');
            });
        } else {
             updateStatus("No audio data recorded to send.");
             console.warn("sendAudioData called with empty Blob.");
             startButton.disabled = false;
             stopButton.disabled = true;
             startButton.classList.remove('recording');
        }
    } else {
         updateStatus("WebSocket is not open. Please wait or refresh.", true);
         console.error("WebSocket is not open. State:", websocket?.readyState);
         startButton.disabled = false;
         stopButton.disabled = true;
         startButton.classList.remove('recording');
    }
}


function processAudioQueue() {
    if (audioQueue.length > 0 && audioContext) {
        if(audioContext.state === 'suspended') {
             console.warn("AudioContext suspended. Attempting to resume...");
             audioContext.resume().then(() => {
                 console.log("AudioContext resumed.");
                 processAudioQueue();
             }).catch(err => {
                 console.error("Failed to resume AudioContext:", err);
                 updateStatus("Error: Could not resume audio playback.", true);
                 isPlaying = false;
                 console.log("Forcing Ready state after AudioContext resume error.");
                 updateStatus("Ready.");
                 startButton.disabled = false;
                 stopButton.disabled = true;
             });
             return;
        }

        isPlaying = true;
        startButton.disabled = true;

        let arrayBuffer = audioQueue.shift();
        const chunkSizeForLog = arrayBuffer.byteLength;
        console.log(`Attempting to decode audio chunk size: ${chunkSizeForLog}`);

        if (!statusDiv.classList.contains('error')) {
             updateStatus("Playing response...");
        }

        audioContext.decodeAudioData(arrayBuffer).then((decodedBuffer) => {
            console.log(`Successfully decoded audio chunk. Duration: ${decodedBuffer.duration.toFixed(3)}s, Channels: ${decodedBuffer.numberOfChannels}, Sample Rate: ${decodedBuffer.sampleRate}`);
            const source = audioContext.createBufferSource();
            source.buffer = decodedBuffer;
            source.connect(audioContext.destination);

            source.onended = () => {
                console.log("Audio chunk finished playing. Queue length:", audioQueue.length);
                if (audioQueue.length === 0) {
                    isPlaying = false;
                    console.log("Finished playing audio queue. Forcing Ready state.");
                    updateStatus("Ready.");
                    startButton.disabled = false;
                    stopButton.disabled = true;
                } else {
                     console.log("Calling processAudioQueue for next chunk.");
                     processAudioQueue();
                }
            };
            source.start(0);
        }).catch((error) => {
            console.error(`Error decoding audio data (chunk size: ${chunkSizeForLog}):`, error);
            if (error instanceof DOMException) {
                 console.error(`DOMException Name: ${error.name}, Message: ${error.message}`);
            }
            updateStatus("Error playing audio chunk.", true);

            isPlaying = false;
            processAudioQueue();
        });
    } else {
         isPlaying = false;
         if (audioQueue.length > 0 && !audioContext) {
             console.error("Audio queue has data but AudioContext is not available.");
             updateStatus("Error: Cannot play audio response.", true);
         }
         if (audioQueue.length === 0) {
             console.log("Queue empty & Playback stopped. Forcing Ready state.");
             updateStatus("Ready.");
             startButton.disabled = false;
             stopButton.disabled = true;
         }
    }
}

startButton.addEventListener('click', startRecording);
stopButton.addEventListener('click', stopRecording);

connectWebSocket();

window.addEventListener('beforeunload', () => {
    if (websocket && websocket.readyState === WebSocket.OPEN) {
        websocket.close(1000, "Page unloaded");
    }
    if (mediaRecorder && mediaRecorder.state === 'recording') {
        mediaRecorder.stop();
    }
});
