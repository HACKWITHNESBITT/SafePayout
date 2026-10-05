import { useState, useCallback } from "react";
import { useNavigate } from "react-router-dom";
import { useMutation } from "@tanstack/react-query";
import { api, queryKeys } from "../api/client";
import { queryClient } from "../main";
import styles from "./NewRun.module.css";

const SAMPLE_CSV = `name,email,amount,currency,note
Amina Diallo,amina.diallo@example.com,480,USD,"40 hrs at \$12/hr"
Brian O'Connor,brian.oconnor@example.com,300,USD,flat fee
Carlos Mendez,carlos.mendez@example.com,1250,USD,project completion
Amina Diallo,amina.diallo@example.com,480,USD,"duplicate entry"
Diana Prince,diana.prince@invalid-email,200,USD,malformed email
Ethan Hunt,ethan.hunt@example.com,5000,USD,unusually large
Fiona Gallagher,fiona.g@example.com,50,USD,small payment
Grace Hopper,grace.hopper@example.com,480,USD,"40 hrs at \$12/hr"`;

const SAMPLE_TEXT = `pay Amina 40 hrs at \$12
Brian flat \$300
Carlos project completion \$1250
Amina again 480 dollars
Diana at diana.prince@invalid-email 200
Ethan \$5000 for the big job
Fiona fifty bucks
Grace 40 hours * 12`;

const LOADING_MESSAGES = [
  "Reading your sheet...",
  "Checking for problems...",
  "Applying rules...",
  "Generating AI explanations...",
  "Almost ready...",
];

export function NewRun() {
  const navigate = useNavigate();
  const [mode, setMode] = useState<"csv" | "text">("csv");
  const [csvFile, setCsvFile] = useState<File | null>(null);
  const [textInput, setTextInput] = useState("");
  const [budgetCap, setBudgetCap] = useState("");
  const [loadingStep, setLoadingStep] = useState(0);
  const [error, setError] = useState<string | null>(null);
  const [isDragOver, setIsDragOver] = useState(false);

  const createRunMutation = useMutation({
    mutationFn: (data: { budget_cap?: string }) => api.createRun(data),
    onSuccess: (run) => {
      queryClient.invalidateQueries({ queryKey: queryKeys.runs(0, 50) });
      if (mode === "csv" && csvFile) {
        uploadFileMutation.mutate({ runId: run.id, file: csvFile });
      } else if (mode === "text" && textInput.trim()) {
        uploadTextMutation.mutate({ runId: run.id, text: textInput });
      } else {
        navigate(`/runs/${run.id}`);
      }
    },
    onError: (err: Error) => {
      setError(err.message);
      setLoadingStep(0);
    },
  });

  const uploadFileMutation = useMutation({
    mutationFn: ({ runId, file }: { runId: number; file: File }) => api.uploadFile(runId, file),
    onMutate: () => {
      setLoadingStep(1);
    },
    onSuccess: (run) => {
      queryClient.invalidateQueries({ queryKey: queryKeys.run(run.id) });
      navigate(`/runs/${run.id}`);
    },
    onError: (err: Error) => {
      setError(err.message);
      setLoadingStep(0);
    },
  });

  const uploadTextMutation = useMutation({
    mutationFn: ({ runId, text }: { runId: number; text: string }) => api.uploadText(runId, text),
    onMutate: () => {
      setLoadingStep(1);
    },
    onSuccess: (run) => {
      queryClient.invalidateQueries({ queryKey: queryKeys.run(run.id) });
      navigate(`/runs/${run.id}`);
    },
    onError: (err: Error) => {
      setError(err.message);
      setLoadingStep(0);
    },
  });

  const handleSubmit = useCallback(
    (e: React.FormEvent) => {
      e.preventDefault();
      setError(null);
      setLoadingStep(0);
      createRunMutation.mutate({ budget_cap: budgetCap || undefined });
    },
    [budgetCap, mode]
  );

  const handleFileChange = useCallback((e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (file) {
      setCsvFile(file);
      setError(null);
    }
  }, []);

  const handleDragOver = useCallback((e: React.DragEvent) => {
    e.preventDefault();
    e.stopPropagation();
    setIsDragOver(true);
  }, []);

  const handleDragLeave = useCallback((e: React.DragEvent) => {
    e.preventDefault();
    e.stopPropagation();
    setIsDragOver(false);
  }, []);

  const handleDrop = useCallback((e: React.DragEvent) => {
    e.preventDefault();
    e.stopPropagation();
    setIsDragOver(false);
    const file = e.dataTransfer.files[0];
    if (file) {
      setCsvFile(file);
      setError(null);
    }
  }, []);

  const loadSample = useCallback(() => {
    if (mode === "csv") {
      const blob = new Blob([SAMPLE_CSV], { type: "text/csv" });
      const file = new File([blob], "messy_payouts.csv", { type: "text/csv" });
      setCsvFile(file);
    } else {
      setTextInput(SAMPLE_TEXT);
    }
    setError(null);
  }, [mode]);

  const isSubmitting = createRunMutation.isPending || uploadFileMutation.isPending || uploadTextMutation.isPending;

  return (
    <div className={styles.container}>
      <div className={styles.card}>
        <header className={styles.header}>
          <h1 className={styles.title}>New Payout Run</h1>
          <p className={styles.subtitle}>Upload a CSV or paste text — AI parses, rules check, you approve.</p>
        </header>

        {error && (
          <div className={styles.error} role="alert">
            <span>⚠</span>
            <span>{error}</span>
            <button onClick={() => setError(null)} className={styles.errorClose} aria-label="Dismiss">✕</button>
          </div>
        )}

        <form onSubmit={handleSubmit} className={styles.form}>
          <div className={styles.tabs} role="tablist" aria-label="Input mode">
            <button
              type="button"
              role="tab"
              aria-selected={mode === "csv"}
              aria-controls="csv-panel"
              className={`${styles.tab} ${mode === "csv" ? styles.active : ""}`}
              onClick={() => setMode("csv")}
            >
              Upload CSV
            </button>
            <button
              type="button"
              role="tab"
              aria-selected={mode === "text"}
              aria-controls="text-panel"
              className={`${styles.tab} ${mode === "text" ? styles.active : ""}`}
              onClick={() => setMode("text")}
            >
              Paste Text
            </button>
          </div>

          <div id="csv-panel" role="tabpanel" hidden={mode !== "csv"} className={styles.panel}>
            <div
              className={`${styles.dropzone} ${isDragOver ? styles.dragOver : ""} ${csvFile ? styles.hasFile : ""}`}
              onDragOver={handleDragOver}
              onDragLeave={handleDragLeave}
              onDrop={handleDrop}
            >
              <input
                type="file"
                id="csv-upload"
                accept=".csv,text/csv"
                onChange={handleFileChange}
                className={styles.fileInput}
                disabled={isSubmitting}
                aria-describedby="csv-hint"
              />
              <label htmlFor="csv-upload" className={styles.dropzoneLabel}>
                {csvFile ? (
                  <>
                    <span className={styles.fileIcon}>📄</span>
                    <span className={styles.fileName}>{csvFile.name}</span>
                    <span className={styles.fileSize}>({(csvFile.size / 1024).toFixed(1)} KB)</span>
                    <button
                      type="button"
                      onClick={() => setCsvFile(null)}
                      className={styles.removeFile}
                      aria-label="Remove file"
                    >
                      ✕
                    </button>
                  </>
                ) : (
                  <>
                    <span className={styles.uploadIcon} aria-hidden="true">⬆</span>
                    <span>Drag & drop a CSV file or click to browse</span>
                  </>
                )}
              </label>
              <p id="csv-hint" className={styles.hint}>
                Expected columns: name, email, amount, currency, note
              </p>
            </div>
          </div>

          <div id="text-panel" role="tabpanel" hidden={mode !== "text"} className={styles.panel}>
            <textarea
              id="text-input"
              value={textInput}
              onChange={(e) => setTextInput(e.target.value)}
              placeholder="e.g. pay Amina 40 hrs at $12, Brian flat $300"
              rows={6}
              className={styles.textarea}
              disabled={isSubmitting}
              aria-describedby="text-hint"
            />
            <p id="text-hint" className={styles.hint}>
              Free-form instructions. AI extracts names, emails, amounts, and notes.
            </p>
          </div>

          <div className={styles.field}>
            <label htmlFor="budget-cap" className={styles.label}>
              Budget Cap (optional)
            </label>
            <div className={styles.inputWrapper}>
              <span className={styles.currencyPrefix}>$</span>
              <input
                type="number"
                id="budget-cap"
                step="0.01"
                min="0"
                value={budgetCap}
                onChange={(e) => setBudgetCap(e.target.value)}
                placeholder="10000.00"
                className={styles.input}
                disabled={isSubmitting}
                aria-describedby="budget-hint"
              />
            </div>
            <p id="budget-hint" className={styles.hint}>
              Maximum total amount for this run. Items exceeding this will be blocked.
            </p>
          </div>

          <div className={styles.actions}>
            <button
              type="button"
              onClick={loadSample}
              className={styles.secondaryBtn}
              disabled={isSubmitting}
            >
              Load Sample Data
            </button>
            <button
              type="submit"
              className={`${styles.primaryBtn} ${isSubmitting ? styles.loading : ""}`}
              disabled={isSubmitting || (!csvFile && !textInput.trim())}
            >
              {isSubmitting && <span className={styles.spinner} aria-hidden="true"></span>}
              <span className={styles.btnText}>
                {isSubmitting ? LOADING_MESSAGES[loadingStep] : "Analyze Payouts"}
              </span>
            </button>
          </div>
        </form>

        {isSubmitting && (
          <div className={styles.progress} role="status" aria-live="polite" aria-label="Processing payouts">
            <div className={styles.progressBar}>
              <div
                className={styles.progressFill}
                style={{ width: `${((loadingStep + 1) / LOADING_MESSAGES.length) * 100}%` }}
              />
            </div>
            <p className={styles.progressText}>{LOADING_MESSAGES[loadingStep]}</p>
          </div>
        )}
      </div>
    </div>
  );
}