"use strict";

/**
 * Friends module for CineTagIt
 */
CineTagIt.modules.friends = function () {
  // Initialize friends list functionality
  initFriendsList();
  // Initialize friend requests functionality
  initFriendRequests();
  // Initialize add friend functionality
  initAddFriend();
};

function initFriendsList() {
  const friendsListContainer = document.getElementById("friends-list-container");
  if (!friendsListContainer) return;

  // Load friends list
  loadFriendsList();

  // Set up event handlers for friend removal
  setupFriendRemoval();
}

function initFriendRequests() {
  const requestsContainer = document.getElementById("friend-requests-container");
  if (!requestsContainer) return;

  // Load friend requests
  loadFriendRequests();

  // Set up event handlers for accepting/rejecting requests
  setupRequestResponses();
}

function initAddFriend() {
  const addFriendContainer = document.getElementById("add-friend-container");
  if (!addFriendContainer) return;

  // Load user's friend code
  loadFriendCode();

  // Set up form for sending friend requests
  setupFriendRequestForm();
}

// API interaction functions
async function loadFriendsList() {
  try {
    const response = await fetch("/api/friends/list");
    const data = await response.json();

    const friendsListContainer = document.getElementById("friends-list-container");

    if (data.success) {
      if (data.friends.length === 0) {
        friendsListContainer.innerHTML = `
                    <p>You don't have any friends yet. <a href="/friends/add">Add a friend</a> to get started!</p>
                `;
        return;
      }

      renderFriendsList(data.friends);
    } else {
      CineTagIt.UI.displayMessage(data.error || "Error loading friends list", "danger");
      friendsListContainer.innerHTML = `<p>Error loading friends list. Please try again later.</p>`;
    }
  } catch (error) {
    console.error("Error loading friends list:", error);
    CineTagIt.UI.displayMessage("Error loading friends list", "danger");
    document.getElementById("friends-list-container").innerHTML = `
            <p>Error loading friends list. Please try again later.</p>
        `;
  }
}

function renderFriendsList(friends) {
  const friendsListContainer = document.getElementById("friends-list-container");

  const friendsHtml = friends
    .map((friend) => {
      const initials = getInitials(friend.display_name || friend.name || "User");

      return `
            <div class="friend-card" data-friend-id="${friend.id}">
                <div class="friend-avatar">${initials}</div>
                <div class="friend-info">
                    <div class="friend-name">${friend.display_name || friend.name || "User"}</div>
                    <div class="friend-since">Friends since ${formatDate(friend.created_at)}</div>
                </div>
                <div class="friend-actions">
                    <button class="view-common-movies-btn">Common Movies</button>
                    <button class="remove-friend-btn" data-friend-id="${friend.id}">Remove</button>
                </div>
            </div>
        `;
    })
    .join("");

  friendsListContainer.innerHTML = friendsHtml;

  // Add event listeners to the remove buttons
  document.querySelectorAll(".remove-friend-btn").forEach((button) => {
    button.addEventListener("click", handleRemoveFriend);
  });

  // Add event listeners to the view common movies buttons
  document.querySelectorAll(".view-common-movies-btn").forEach((button) => {
    button.addEventListener("click", handleViewCommonMovies);
  });
}

async function loadFriendRequests() {
  try {
    const response = await fetch("/api/friends/requests");
    const data = await response.json();

    const requestsContainer = document.getElementById("friend-requests-container");

    if (data.success) {
      if (data.requests.length === 0) {
        requestsContainer.innerHTML = `
                    <p>You don't have any pending friend requests.</p>
                `;
        return;
      }

      renderFriendRequests(data.requests);
    } else {
      CineTagIt.UI.displayMessage(data.error || "Error loading friend requests", "danger");
      requestsContainer.innerHTML = `<p>Error loading friend requests. Please try again later.</p>`;
    }
  } catch (error) {
    console.error("Error loading friend requests:", error);
    CineTagIt.UI.displayMessage("Error loading friend requests", "danger");
    document.getElementById("friend-requests-container").innerHTML = `
            <p>Error loading friend requests. Please try again later.</p>
        `;
  }
}

function renderFriendRequests(requests) {
  const requestsContainer = document.getElementById("friend-requests-container");
  if (!requestsContainer) return;

  if (requests.length === 0) {
    requestsContainer.innerHTML = `<p>You don't have any pending friend requests.</p>`;
    return;
  }

  const requestsHtml = requests
    .map((request) => {
      const initials = getInitials(request.display_name || "User");
      const isReceived = request.type === "received";

      return `
            <div class="request-card" data-request-id="${request.id}">
                <div class="friend-avatar">${initials}</div>
                <div class="request-info">
                    <div class="friend-name">${request.display_name || "User"}</div>
                    <div class="request-type text-muted small">${isReceived ? "Received" : "Sent"}</div>
                    <div class="request-date">Requested on ${formatDate(request.created_at)}</div>
                </div>
                <div class="request-actions">
                    ${
                      isReceived
                        ? `
                        <button class="accept-request-btn" data-request-id="${request.id}">Accept</button>
                        <button class="reject-request-btn" data-request-id="${request.id}">Reject</button>
                    `
                        : `
                        <button class="cancel-request-btn" data-request-id="${request.id}">Cancel</button>
                    `
                    }
                </div>
            </div>
        `;
    })
    .join("");

  requestsContainer.innerHTML = requestsHtml;

  // Add event listeners to the accept/reject buttons
  document.querySelectorAll(".accept-request-btn").forEach((button) => {
    button.addEventListener("click", handleAcceptRequest);
  });

  document.querySelectorAll(".reject-request-btn").forEach((button) => {
    button.addEventListener("click", handleRejectRequest);
  });

  // Add event listeners to the cancel buttons
  document.querySelectorAll(".cancel-request-btn").forEach((button) => {
    button.addEventListener("click", handleCancelRequest);
  });
}

async function loadFriendCode() {
  try {
    const response = await fetch("/api/friends/code");
    const data = await response.json();

    const friendCodeElement = document.getElementById("friend-code");

    if (data.success) {
      friendCodeElement.textContent = data.friend_code;
    } else {
      CineTagIt.UI.displayMessage(data.error || "Error loading friend code", "danger");
      friendCodeElement.textContent = "Error loading friend code";
    }
  } catch (error) {
    console.error("Error loading friend code:", error);
    CineTagIt.UI.displayMessage("Error loading friend code", "danger");
    document.getElementById("friend-code").textContent = "Error loading friend code";
  }
}

function setupFriendRequestForm() {
  const sendRequestButton = document.getElementById("send-request-button");
  const friendCodeInput = document.getElementById("friend-code-input");

  if (!sendRequestButton || !friendCodeInput) return;

  sendRequestButton.addEventListener("click", async () => {
    const friendCode = friendCodeInput.value.trim();

    if (!friendCode) {
      CineTagIt.UI.displayMessage("Please enter a friend code", "warning");
      return;
    }

    try {
      const response = await fetch("/api/friends/request", {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          "X-CSRF-TOKEN": CineTagIt.Utils.getCsrfToken(),
        },
        body: JSON.stringify({ friend_code: friendCode }),
      });

      const data = await response.json();

      if (data.success) {
        CineTagIt.UI.displayMessage(data.message || "Friend request sent successfully", "success");
        friendCodeInput.value = "";
      } else {
        CineTagIt.UI.displayMessage(data.error || "Error sending friend request", "danger");
      }
    } catch (error) {
      console.error("Error sending friend request:", error);
      CineTagIt.UI.displayMessage("Error sending friend request", "danger");
    }
  });
}

function setupFriendRemoval() {
  // Event delegation is used in renderFriendsList
}

function setupRequestResponses() {
  // Event delegation is used in renderFriendRequests
}

async function handleRemoveFriend(event) {
  const friendId = event.target.dataset.friendId;

  if (!confirm("Are you sure you want to remove this friend?")) {
    return;
  }

  try {
    const response = await fetch(`/api/friends/${friendId}`, {
      method: "DELETE",
      headers: {
        "X-CSRF-TOKEN": CineTagIt.Utils.getCsrfToken(),
      },
    });

    const data = await response.json();

    if (data.success) {
      CineTagIt.UI.displayMessage(data.message || "Friend removed successfully", "success");
      // Remove the friend card from the DOM
      const friendCard = document.querySelector(`.friend-card[data-friend-id="${friendId}"]`);
      if (friendCard) {
        friendCard.remove();
      }

      // If no friends left, show the empty state
      const friendsListContainer = document.getElementById("friends-list-container");
      if (friendsListContainer.children.length === 0) {
        friendsListContainer.innerHTML = `
                    <p>You don't have any friends yet. <a href="/friends/add">Add a friend</a> to get started!</p>
                `;
      }
    } else {
      CineTagIt.UI.displayMessage(data.error || "Error removing friend", "danger");
    }
  } catch (error) {
    console.error("Error removing friend:", error);
    CineTagIt.UI.displayMessage("Error removing friend", "danger");
  }
}

function handleViewCommonMovies(event) {
  const friendCard = event.target.closest(".friend-card");
  const friendId = friendCard.dataset.friendId;

  // Redirect to the common movies page
  window.location.href = `/movies?friend_id=${friendId}`;
}

async function handleAcceptRequest(event) {
  const requestId = event.target.dataset.requestId;

  try {
    const response = await fetch(`/api/friends/requests/${requestId}/respond`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        "X-CSRF-TOKEN": CineTagIt.Utils.getCsrfToken(),
      },
      body: JSON.stringify({ action: "accept" }),
    });

    const data = await response.json();

    if (data.success) {
      CineTagIt.UI.displayMessage(data.message || "Friend request accepted", "success");
      // Remove the request card from the DOM
      const requestCard = document.querySelector(`.request-card[data-request-id="${requestId}"]`);
      if (requestCard) {
        requestCard.remove();
      }

      // If no requests left, show the empty state
      const requestsContainer = document.getElementById("friend-requests-container");
      if (requestsContainer.children.length === 0) {
        requestsContainer.innerHTML = `
                    <p>You don't have any pending friend requests.</p>
                `;
      }
    } else {
      CineTagIt.UI.displayMessage(data.error || "Error accepting friend request", "danger");
    }
  } catch (error) {
    console.error("Error accepting friend request:", error);
    CineTagIt.UI.displayMessage("Error accepting friend request", "danger");
  }
}

async function handleRejectRequest(event) {
  const requestId = event.target.dataset.requestId;

  try {
    const response = await fetch(`/api/friends/requests/${requestId}/respond`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        "X-CSRF-TOKEN": CineTagIt.Utils.getCsrfToken(),
      },
      body: JSON.stringify({ action: "reject" }),
    });

    const data = await response.json();

    if (data.success) {
      CineTagIt.UI.displayMessage(data.message || "Friend request rejected", "success");
      // Remove the request card from the DOM
      const requestCard = document.querySelector(`.request-card[data-request-id="${requestId}"]`);
      if (requestCard) {
        requestCard.remove();
      }

      // If no requests left, show the empty state
      const requestsContainer = document.getElementById("friend-requests-container");
      if (requestsContainer && requestsContainer.querySelectorAll(".request-card").length === 0) {
        requestsContainer.innerHTML = `
                    <p>You don't have any pending friend requests.</p>
                `;
      }
    } else {
      CineTagIt.UI.displayMessage(data.error || "Error rejecting friend request", "danger");
    }
  } catch (error) {
    console.error("Error rejecting friend request:", error);
    CineTagIt.UI.displayMessage("Error rejecting friend request", "danger");
  }
}

async function handleCancelRequest(event) {
  const requestId = event.target.dataset.requestId;

  if (!confirm("Are you sure you want to cancel this friend request?")) {
    return;
  }

  try {
    const response = await fetch(`/api/friends/requests/${requestId}`, {
      method: "DELETE",
      headers: {
        "X-CSRF-TOKEN": CineTagIt.Utils.getCsrfToken(),
      },
    });

    const data = await response.json();

    if (data.success) {
      CineTagIt.UI.displayMessage(data.message || "Friend request cancelled", "success");
      // Remove the request card from the DOM
      const requestCard = document.querySelector(`.request-card[data-request-id="${requestId}"]`);
      if (requestCard) {
        requestCard.remove();
      }

      // If no requests left, show the empty state
      const requestsContainer = document.getElementById("friend-requests-container");
      if (requestsContainer && requestsContainer.querySelectorAll(".request-card").length === 0) {
        requestsContainer.innerHTML = `
                    <p>You don't have any pending friend requests.</p>
                `;
      }
    } else {
      CineTagIt.UI.displayMessage(data.error || "Error cancelling friend request", "danger");
    }
  } catch (error) {
    console.error("Error cancelling friend request:", error);
    CineTagIt.UI.displayMessage("Error cancelling friend request", "danger");
  }
}

// Helper functions
function getInitials(name) {
  return name
    .split(" ")
    .map((part) => part.charAt(0))
    .join("")
    .toUpperCase()
    .substring(0, 2);
}

function formatDate(dateString) {
  const date = new Date(dateString);
  return date.toLocaleDateString();
}
