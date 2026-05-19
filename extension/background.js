/**
 * CMYGO Capture — Background Service Worker
 *
 * Handles download requests from the content script.
 * Downloads images and metadata JSON to Downloads/cmygo/ directory.
 */

// Default download subdirectory
const DOWNLOAD_DIR = "cmygo";

// -----------------------------------------------------------------------
// Message handler
// -----------------------------------------------------------------------

chrome.runtime.onMessage.addListener((message, sender, sendResponse) => {
  if (message.action === "capture") {
    handleCapture(message.data)
      .then((result) => sendResponse(result))
      .catch((err) =>
        sendResponse({ success: false, error: err.message })
      );
    // Return true to indicate async response
    return true;
  }

  if (message.action === "getStats") {
    getStats().then((stats) => sendResponse(stats));
    return true;
  }
});

// -----------------------------------------------------------------------
// Capture handler
// -----------------------------------------------------------------------

async function handleCapture(data) {
  const { twitter_id, tweet_url, tweet_text, tweet_time, images, captured_at } =
    data;

  if (!twitter_id || !images || images.length === 0) {
    return { success: false, error: "Missing twitter_id or images" };
  }

  const timestamp = Math.floor(Date.now() / 1000);
  const downloadIds = [];

  // Download each image
  for (let i = 0; i < images.length; i++) {
    const imageUrl = images[i];

    // Determine file extension from URL
    let ext = "jpg";
    const formatMatch = imageUrl.match(/format=(\w+)/);
    if (formatMatch) {
      ext = formatMatch[1];
    } else if (imageUrl.includes(".png")) {
      ext = "png";
    }

    // Filename: twitter-{username}-{timestamp}-{index}.{ext}
    // This format is compatible with CMYGO's existing rename regex
    const filename = `${DOWNLOAD_DIR}/twitter-${twitter_id}-${timestamp}-${i + 1}.${ext}`;

    try {
      const downloadId = await downloadFile(imageUrl, filename);
      downloadIds.push(downloadId);
    } catch (err) {
      console.error(`[CMYGO] Failed to download image ${i + 1}:`, err);
      return {
        success: false,
        error: `Failed to download image ${i + 1}: ${err.message}`,
      };
    }
  }

  // Save metadata JSON
  const metadata = {
    twitter_id,
    tweet_url,
    tweet_text,
    tweet_time,
    images: images.length,
    image_filenames: downloadIds.map((_, i) => {
      let ext = "jpg";
      const formatMatch = images[i].match(/format=(\w+)/);
      if (formatMatch) ext = formatMatch[1];
      return `twitter-${twitter_id}-${timestamp}-${i + 1}.${ext}`;
    }),
    captured_at,
  };

  const jsonFilename = `${DOWNLOAD_DIR}/twitter-${twitter_id}-${timestamp}.json`;
  await downloadJson(metadata, jsonFilename);

  // Update capture count in storage
  await incrementCaptureCount(images.length);

  return {
    success: true,
    downloaded: downloadIds.length,
    metadata_file: jsonFilename,
  };
}

// -----------------------------------------------------------------------
// Download helpers
// -----------------------------------------------------------------------

/**
 * Download a file using chrome.downloads API.
 * Returns a Promise that resolves with the download ID.
 */
function downloadFile(url, filename) {
  return new Promise((resolve, reject) => {
    chrome.downloads.download(
      {
        url: url,
        filename: filename,
        saveAs: false,
        conflictAction: "uniquify",
      },
      (downloadId) => {
        if (chrome.runtime.lastError) {
          reject(new Error(chrome.runtime.lastError.message));
        } else {
          resolve(downloadId);
        }
      }
    );
  });
}

/**
 * Download a JSON object as a file.
 * Creates a data URI and downloads it.
 */
function downloadJson(data, filename) {
  const jsonStr = JSON.stringify(data, null, 2);
  const dataUrl =
    "data:application/json;charset=utf-8," +
    encodeURIComponent(jsonStr);

  return new Promise((resolve, reject) => {
    chrome.downloads.download(
      {
        url: dataUrl,
        filename: filename,
        saveAs: false,
        conflictAction: "overwrite",
      },
      (downloadId) => {
        if (chrome.runtime.lastError) {
          reject(new Error(chrome.runtime.lastError.message));
        } else {
          resolve(downloadId);
        }
      }
    );
  });
}

// -----------------------------------------------------------------------
// Stats tracking
// -----------------------------------------------------------------------

async function incrementCaptureCount(imageCount) {
  const result = await chrome.storage.local.get(["captureStats"]);
  const stats = result.captureStats || { total: 0, today: 0, todayDate: "" };

  const today = new Date().toISOString().slice(0, 10);
  if (stats.todayDate !== today) {
    stats.today = 0;
    stats.todayDate = today;
  }

  stats.total += imageCount;
  stats.today += imageCount;

  await chrome.storage.local.set({ captureStats: stats });
}

async function getStats() {
  const result = await chrome.storage.local.get(["captureStats"]);
  const stats = result.captureStats || { total: 0, today: 0, todayDate: "" };

  const today = new Date().toISOString().slice(0, 10);
  if (stats.todayDate !== today) {
    stats.today = 0;
  }

  return stats;
}
