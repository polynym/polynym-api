// The access token is held in memory only, never in localStorage,
// so it does not outlive the page.
let accessToken = null;
let currentUser = null;
let writableIdentity = null;

const statusEl = document.getElementById("status");
const outputEl = document.getElementById("output");
const queryBtn = document.getElementById("query-btn");
const eraseBtn = document.getElementById("erase-btn");
const loginForm = document.getElementById("login-form");
const loggedInPanel = document.getElementById("logged-in-panel");
const loggedInUser = document.getElementById("logged-in-user");
const logoutBtn = document.getElementById("logout-btn");
const writePanel = document.getElementById("write-panel");
const writeDescription = document.getElementById("write-description");
const currentIdentityValue = document.getElementById("current-identity-value");
const writeForm = document.getElementById("write-form");
const identityValueInput = document.getElementById("identity-value");
loginForm.hidden = false;
loggedInPanel.hidden = true;
queryBtn.disabled = true;
eraseBtn.disabled = true;
writePanel.hidden = true;
const demoApp = document.getElementById("demo-app");
const demoPersonId = demoApp.dataset.personId;
const passwordInput = document.getElementById("password");
const togglePasswordBtn = document.getElementById("toggle-password");
togglePasswordBtn.addEventListener("click", () => {
  const passwordIsHidden = passwordInput.type === "password";

  passwordInput.type = passwordIsHidden ? "text" : "password";
  togglePasswordBtn.textContent = passwordIsHidden ? "Hide" : "Show";
  togglePasswordBtn.setAttribute(
    "aria-label",
    passwordIsHidden ? "Hide password" : "Show password",
  );
});

loginForm.addEventListener("submit", async (event) => {
  event.preventDefault();

  const username = document.getElementById("username").value.trim();
  const password = passwordInput.value;

  statusEl.textContent = "Logging in as " + username + "...";
  outputEl.textContent = "{}";

  try {
    const response = await fetch("/api/token/", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ username, password }),
    });

    if (!response.ok) {
      throw new Error("Login failed: HTTP " + response.status);
    }

    const data = await response.json();
    accessToken = data.access;
    currentUser = username;
    writableIdentity = null;

    loginForm.hidden = true;
    loggedInPanel.hidden = false;
    writePanel.hidden = true;
    loggedInUser.textContent = username;

    identityValueInput.value = "";
    currentIdentityValue.textContent = "";
    writeDescription.textContent = "";

    queryBtn.disabled = !demoPersonId;
    eraseBtn.disabled = username !== "zoe_self" || !demoPersonId;

    if (demoPersonId) {
      statusEl.textContent = "Logged in successfully as " + username + ".";
    } else {
      statusEl.textContent =
        "Logged in, but the demonstration person does not exist. " +
        "Run 'python manage.py seed_demo' and reload this page.";
    }
  } catch (error) {
    accessToken = null;
    currentUser = null;
    writableIdentity = null;

    loginForm.hidden = false;
    loggedInPanel.hidden = true;
    writePanel.hidden = true;

    identityValueInput.value = "";
    currentIdentityValue.textContent = "";
    writeDescription.textContent = "";

    queryBtn.disabled = true;
    eraseBtn.disabled = true;

    statusEl.textContent = "Error: " + error.message;
  } finally {
    passwordInput.value = "";
    passwordInput.type = "password";
    togglePasswordBtn.textContent = "Show";
    togglePasswordBtn.setAttribute("aria-label", "Show password");
  }
});

logoutBtn.addEventListener("click", () => {
  accessToken = null;
  currentUser = null;
  writableIdentity = null;

  loginForm.hidden = false;
  loggedInPanel.hidden = true;
  writePanel.hidden = true;
  loggedInUser.textContent = "";

  document.getElementById("username").value = "";
  identityValueInput.value = "";
  currentIdentityValue.textContent = "";
  writeDescription.textContent = "";

  queryBtn.disabled = true;
  eraseBtn.disabled = true;

  outputEl.textContent = "{}";
  statusEl.textContent = "Logged out.";
});

queryBtn.addEventListener("click", async () => {
  statusEl.textContent = "Querying identity endpoint as " + currentUser + "...";
  outputEl.textContent = "{}";

  try {
    const response = await fetch(
      "/api/persons/" + demoPersonId + "/identity/",
      {
        headers: { Authorization: "Bearer " + accessToken },
      },
    );

    const data = await response.json();

    writableIdentity = null;
    writePanel.hidden = true;
    identityValueInput.value = "";
    currentIdentityValue.textContent = "";
    writeDescription.textContent = "";

    if (response.ok) {
      if (currentUser === "zoe_self") {
        writableIdentity = data.identities.find(
          (identity) => identity.type === "preferred",
        );

        if (writableIdentity) {
          writeDescription.textContent =
            "You can update your preferred identity.";
        }
      } else if (currentUser === "hr_user") {
        writableIdentity = data.identities.find(
          (identity) => identity.type === "legal",
        );

        if (writableIdentity) {
          writeDescription.textContent = "HR can update the legal identity.";
        }
      }

      if (writableIdentity) {
        currentIdentityValue.textContent = writableIdentity.value;
        writePanel.hidden = false;
      }
    }

    statusEl.textContent = "Request complete. HTTP status: " + response.status;
    outputEl.textContent = JSON.stringify(data, null, 2);
  } catch (error) {
    statusEl.textContent = "Error: " + error.message;
  }
});

writeForm.addEventListener("submit", async (event) => {
  event.preventDefault();

  if (!writableIdentity) {
    statusEl.textContent = "No writable identity is available.";
    return;
  }

  const newValue = identityValueInput.value.trim();

  if (!newValue) {
    statusEl.textContent = "Enter a new identity value.";
    return;
  }

  statusEl.textContent = "Updating " + writableIdentity.type + " identity...";

  try {
    const response = await fetch(
      "/api/identities/" + writableIdentity.id + "/",
      {
        method: "PUT",
        headers: {
          Authorization: "Bearer " + accessToken,
          "Content-Type": "application/json",
        },
        body: JSON.stringify({
          type: writableIdentity.type,
          value: newValue,
          context_tag: writableIdentity.context_tag,
          language_code: writableIdentity.language_code,
          script_code: writableIdentity.script_code,
        }),
      },
    );

    const data = await response.json();

    if (!response.ok) {
      statusEl.textContent = "Update failed. HTTP status: " + response.status;
      outputEl.textContent = JSON.stringify(data, null, 2);
      return;
    }

    writableIdentity = data;
    currentIdentityValue.textContent = data.value;
    identityValueInput.value = "";

    statusEl.textContent =
      "Identity updated successfully. HTTP status: " + response.status;
    outputEl.textContent = JSON.stringify(data, null, 2);
  } catch (error) {
    statusEl.textContent = "Error: " + error.message;
  }
});

eraseBtn.addEventListener("click", async () => {
  const confirmed = confirm(
    "This permanently deletes the seeded person record. " +
      "Run 'python manage.py seed_demo' to recreate it. Continue?",
  );

  if (!confirmed) {
    return;
  }

  statusEl.textContent = "Requesting erasure as " + currentUser + "...";
  outputEl.textContent = "{}";

  try {
    const response = await fetch("/api/persons/" + demoPersonId + "/", {
      method: "DELETE",
      headers: { Authorization: "Bearer " + accessToken },
    });

    statusEl.textContent =
      "Erasure request complete. HTTP status: " + response.status;

    if (response.status === 204) {
      outputEl.textContent =
        "204 No Content\n\nThe person record and all associated " +
        "identity records have been deleted.\nQuerying any role now " +
        "returns HTTP 404.";
    } else {
      const body = await response.json();
      outputEl.textContent = JSON.stringify(body, null, 2);
    }
  } catch (error) {
    statusEl.textContent = "Error: " + error.message;
  }
});
