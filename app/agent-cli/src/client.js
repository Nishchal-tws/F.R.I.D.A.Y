import WebSocket from 'ws';

export class FridayClient {
  constructor(config) {
    this.config = config;
    this.ws = null;
    this.pendingChat = null;     // will hold { resolve, reject } of the in-flight chat
    this.approvalHandler = null; // async (tool, args) => boolean
  }

  // GET /info -> parsed JSON
  async info() {
    const response = await fetch(`${this.config.httpUrl}/info`);

    if (!response.ok) {
      throw new Error(`HTTP error! Status: ${response.status}`);
    }

    return await response.json();
  }

  // Resolves when the socket is open, rejects if it can't connect.
  connect() {
    return new Promise((resolve, reject) => {
      this.ws = new WebSocket(this.config.wsUrl);
      
      const opOpen = () => {
      this.ws.off('error', onError);
      this._attachListeners();
      this.ws.on('error', () => {});
      
      resolve(); 
      };

      const onError = (err) => {
      this.ws.off('open', onOpen);
      reject(err); 
      };
      
      this.ws.once('open', onOpen);
      this.ws.once('error', onError);

      });
  }

  // Send a prompt; resolves with the final answer text.
  chat(text) {
    // TODO: if this.pendingChat is already set, return Promise.reject(new Error('A chat is already running'))
    return new Promise((resolve, reject) => {
      // TODO: this.pendingChat = { resolve, reject };
      // TODO: this.ws.send(JSON.stringify({ type: 'chat', text }));
    });
  }

  onApproval(handler) {
    this.approvalHandler = handler;
  }

  close() {
    // TODO: close the socket if it exists
  }

  // ---- internals ----

  _attachListeners() {
    this.ws.on('message', (data) => this._onMessage(data));
    this.ws.on('close', () => this._onClose());
  }

  _onMessage(data) {
    let msg;
    try {
      msg = JSON.parse(data.toString()); // data is a Buffer, not a string
    } catch {
      return; // ignore garbage
    }

    switch (msg.type) {
      case 'answer':
        // TODO: resolve pendingChat with msg.text, then set pendingChat = null
        break;
      case 'error':
        // TODO: reject pendingChat with new Error(msg.message), then clear it
        break;
      case 'approval_request':
        this._handleApproval(msg);
        break;
      default:
        break; // unknown types are ignored on purpose (forward compatible)
    }
  }

  async _handleApproval(msg) {
    let approved = false;
    try {
      // TODO: const result = await this.approvalHandler(msg.tool, msg.arguments);
      // TODO: approved = (result === true);   // anything but a real `true` is a no
    } catch {
      approved = false;
    }
    // ALWAYS reply, even on failure, or the Python side waits forever.
    // TODO: this.ws.send(JSON.stringify({ type: 'approval_response', id: msg.id, approved }));
  }

  _onClose() {
    // TODO: if pendingChat is set, reject it with new Error('Connection lost'), then clear it
  }
}