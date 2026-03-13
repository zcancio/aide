/**
 * Browser fingerprint generation and storage for anonymous users.
 */

const FINGERPRINT_KEY = "aide_fingerprint_id";

/**
 * Get or create a browser fingerprint ID.
 * @returns {string} The fingerprint ID
 */
export function getFingerprint() {
  let id = localStorage.getItem(FINGERPRINT_KEY);
  if (!id) {
    id = crypto.randomUUID();
    localStorage.setItem(FINGERPRINT_KEY, id);
  }
  return id;
}

/**
 * Clear the stored fingerprint ID.
 */
export function clearFingerprint() {
  localStorage.removeItem(FINGERPRINT_KEY);
}
