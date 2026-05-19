/**
 * CMYGO Capture — Content Script
 *
 * Injects a capture button (📦) into tweets on x.com/twitter.com.
 * Extracts: author username, tweet text, image URLs, tweet URL.
 * Sends data to the background service worker for download.
 */

(function () {
  "use strict";

  const BUTTON_CLASS = "cmygo-capture-btn";
  const CAPTURED_ATTR = "data-cmygo-captured";

  // -----------------------------------------------------------------------
  // DOM extraction helpers
  // -----------------------------------------------------------------------

  /**
   * Find the closest ancestor tweet article from any element inside a tweet.
   */
  function findTweetArticle(el) {
    return el.closest('article[data-testid="tweet"]');
  }

  /**
   * Extract the author username from a tweet article.
   * Looks for the @username pattern inside data-testid="User-Name".
   */
  function extractUsername(article) {
    const userNameEl = article.querySelector('[data-testid="User-Name"]');
    if (!userNameEl) return null;

    // The username link contains href like "/username"
    const links = userNameEl.querySelectorAll("a[href]");
    for (const link of links) {
      const href = link.getAttribute("href");
      // Match /{username} but not /status/ etc.
      const m = href && href.match(/^\/([A-Za-z0-9_]+)$/);
      if (m) return m[1];
    }
    return null;
  }

  /**
   * Extract tweet text content.
   */
  function extractTweetText(article) {
    const textEl = article.querySelector('[data-testid="tweetText"]');
    return textEl ? textEl.innerText.trim() : "";
  }

  /**
   * Extract image URLs from a tweet (original quality).
   * Returns array of image URLs with :orig quality.
   */
  function extractImageUrls(article) {
    const urls = [];
    const photoContainers = article.querySelectorAll(
      '[data-testid="tweetPhoto"]'
    );

    for (const container of photoContainers) {
      const img = container.querySelector("img");
      if (!img || !img.src) continue;

      let url = img.src;

      // Upgrade to original quality
      // Twitter image URLs: https://pbs.twimg.com/media/xxx?format=jpg&name=small
      // We want: https://pbs.twimg.com/media/xxx?format=jpg&name=orig
      if (url.includes("pbs.twimg.com/media/")) {
        url = url.replace(/[?&]name=[^&]+/, "");
        url += (url.includes("?") ? "&" : "?") + "name=orig";
      }

      urls.push(url);
    }
    return urls;
  }

  /**
   * Extract the tweet permalink URL.
   */
  function extractTweetUrl(article) {
    // Look for the timestamp link which contains the permalink
    const timeEl = article.querySelector("time[datetime]");
    if (timeEl) {
      const link = timeEl.closest("a[href]");
      if (link) {
        const href = link.getAttribute("href");
        if (href && href.includes("/status/")) {
          return "https://x.com" + href;
        }
      }
    }
    return window.location.href;
  }

  /**
   * Extract tweet timestamp.
   */
  function extractTimestamp(article) {
    const timeEl = article.querySelector("time[datetime]");
    return timeEl ? timeEl.getAttribute("datetime") : null;
  }

  // -----------------------------------------------------------------------
  // Button injection
  // -----------------------------------------------------------------------

  /**
   * Create the capture button element.
   */
  function createCaptureButton() {
    const btn = document.createElement("button");
    btn.className = BUTTON_CLASS;
    btn.textContent = "📦";
    btn.title = "CMYGO: 捕获品書";
    btn.setAttribute("type", "button");
    return btn;
  }

  /**
   * Handle capture button click.
   */
  async function handleCapture(event) {
    event.preventDefault();
    event.stopPropagation();

    const btn = event.currentTarget;
    const article = findTweetArticle(btn);
    if (!article) return;

    // Prevent double capture
    if (article.getAttribute(CAPTURED_ATTR) === "true") {
      btn.textContent = "✅";
      return;
    }

    const username = extractUsername(article);
    const tweetText = extractTweetText(article);
    const imageUrls = extractImageUrls(article);
    const tweetUrl = extractTweetUrl(article);
    const tweetTime = extractTimestamp(article);

    if (!username) {
      btn.textContent = "❌";
      btn.title = "无法提取用户名";
      setTimeout(() => {
        btn.textContent = "📦";
        btn.title = "CMYGO: 捕获品書";
      }, 2000);
      return;
    }

    if (imageUrls.length === 0) {
      btn.textContent = "❌";
      btn.title = "推文中没有图片";
      setTimeout(() => {
        btn.textContent = "📦";
        btn.title = "CMYGO: 捕获品書";
      }, 2000);
      return;
    }

    // Show loading state
    btn.textContent = "⏳";
    btn.disabled = true;

    try {
      // Send to background script
      const response = await chrome.runtime.sendMessage({
        action: "capture",
        data: {
          twitter_id: username.toLowerCase(),
          tweet_url: tweetUrl,
          tweet_text: tweetText,
          tweet_time: tweetTime,
          images: imageUrls,
          captured_at: new Date().toISOString(),
        },
      });

      if (response && response.success) {
        article.setAttribute(CAPTURED_ATTR, "true");
        btn.textContent = "✅";
        btn.title = `已捕获 ${imageUrls.length} 张图片`;
        btn.classList.add("cmygo-captured");
      } else {
        throw new Error(response?.error || "Unknown error");
      }
    } catch (err) {
      console.error("[CMYGO] Capture failed:", err);
      btn.textContent = "❌";
      btn.title = "捕获失败: " + err.message;
      btn.disabled = false;
      setTimeout(() => {
        btn.textContent = "📦";
        btn.title = "CMYGO: 捕获品書";
      }, 3000);
    }
  }

  /**
   * Inject capture button into a tweet article if it has images and
   * doesn't already have a button.
   */
  function injectButton(article) {
    // Skip if already has button
    if (article.querySelector("." + BUTTON_CLASS)) return;

    // Only inject if tweet has images
    const hasImages = article.querySelector('[data-testid="tweetPhoto"]');
    if (!hasImages) return;

    // Find the action bar (like, retweet, etc.) to insert our button nearby
    const actionBar = article.querySelector('[role="group"]');
    if (!actionBar) return;

    const btn = createCaptureButton();
    btn.addEventListener("click", handleCapture);

    // Insert before the action bar
    actionBar.parentNode.insertBefore(btn, actionBar);
  }

  // -----------------------------------------------------------------------
  // Observer — detect new tweets as user scrolls
  // -----------------------------------------------------------------------

  function scanAndInject() {
    const articles = document.querySelectorAll('article[data-testid="tweet"]');
    for (const article of articles) {
      injectButton(article);
    }
  }

  // Initial scan
  scanAndInject();

  // Watch for new tweets (infinite scroll, navigation)
  const observer = new MutationObserver(() => {
    scanAndInject();
  });

  observer.observe(document.body, {
    childList: true,
    subtree: true,
  });
})();
