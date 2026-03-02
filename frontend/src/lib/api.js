/**
 * API client for AIde backend
 * All functions return { data } on success or { error } on failure
 * Never throws - errors are returned as { error }
 */

async function apiCall(url, options = {}) {
  try {
    const response = await fetch(url, {
      ...options,
      credentials: 'same-origin',
    });

    const data = await response.json();

    if (response.ok) {
      return { data };
    } else {
      return { error: data.detail || response.statusText };
    }
  } catch (err) {
    return { error: err.message || 'Network error' };
  }
}

export async function fetchAides() {
  return apiCall('/api/aides');
}

export async function fetchAide(aideId) {
  return apiCall(`/api/aides/${aideId}`);
}

export async function createAide(payload = {}) {
  return apiCall('/api/aides', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
  });
}

export async function updateAide(aideId, payload) {
  return apiCall(`/api/aides/${aideId}`, {
    method: 'PATCH',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
  });
}

export async function archiveAide(aideId) {
  return apiCall(`/api/aides/${aideId}/archive`, {
    method: 'POST',
  });
}

export async function deleteAide(aideId) {
  return apiCall(`/api/aides/${aideId}`, {
    method: 'DELETE',
  });
}

export async function sendMessage(payload) {
  return apiCall('/api/message', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
  });
}

export async function publishAide(aideId, slug) {
  return apiCall(`/api/aides/${aideId}/publish`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ slug }),
  });
}

export async function unpublishAide(aideId) {
  return apiCall(`/api/aides/${aideId}/unpublish`, {
    method: 'POST',
  });
}

export async function sendMagicLink(email) {
  return apiCall('/auth/send', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ email }),
  });
}

export async function verifyToken(token) {
  return apiCall(`/auth/verify?token=${token}`);
}

export async function fetchMe() {
  return apiCall('/auth/me');
}

export async function logout() {
  return apiCall('/auth/logout', {
    method: 'POST',
  });
}
