export class BrowserTts {
  private listeners = new Set<(speaking: boolean) => void>();

  subscribe(listener: (speaking: boolean) => void): () => void {
    this.listeners.add(listener);
    return () => {
      this.listeners.delete(listener);
    };
  }

  speak(text: string): void {
    if (!("speechSynthesis" in window)) {
      return;
    }

    window.speechSynthesis.cancel();
    const utterance = new SpeechSynthesisUtterance(text);
    utterance.onstart = () => this.emit(true);
    utterance.onend = () => this.emit(false);
    utterance.onerror = () => this.emit(false);
    window.speechSynthesis.speak(utterance);
  }

  stop(): void {
    if ("speechSynthesis" in window) {
      window.speechSynthesis.cancel();
    }
    this.emit(false);
  }

  private emit(value: boolean): void {
    for (const listener of this.listeners) {
      listener(value);
    }
  }
}
