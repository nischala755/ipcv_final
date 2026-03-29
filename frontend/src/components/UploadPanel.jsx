import { useRef } from "react";

export default function UploadPanel({ onFileSelected, loading }) {
  const inputRef = useRef(null);

  const handleDrop = (event) => {
    event.preventDefault();
    if (loading) return;
    const file = event.dataTransfer.files?.[0];
    if (file) onFileSelected(file);
  };

  const preventDefaults = (event) => {
    event.preventDefault();
    event.stopPropagation();
  };

  return (
    <section
      className="upload-card"
      onDragEnter={preventDefaults}
      onDragOver={preventDefaults}
      onDrop={handleDrop}
    >
      <h2>Drop media to inspect authenticity</h2>
      <p>Supports image and video inputs. Detection logic is IPCV-only and deterministic.</p>
      <div className="upload-actions">
        <button disabled={loading} onClick={() => inputRef.current?.click()}>
          {loading ? "Analyzing..." : "Choose File"}
        </button>
        <span>or drag and drop here</span>
      </div>
      <input
        ref={inputRef}
        type="file"
        accept="image/*,video/*"
        hidden
        onChange={(e) => {
          const file = e.target.files?.[0];
          if (file) onFileSelected(file);
        }}
      />
    </section>
  );
}
