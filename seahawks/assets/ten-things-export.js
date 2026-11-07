(function () {
  "use strict";

  function boot() {
    var section = document.getElementById("watch");
    if (!section || !section.querySelector(".watch article")) return;
    if (section.querySelector(".watch-export-actions")) return;

    var heading = section.querySelector("h2");
    var cards = Array.from(section.querySelectorAll(".watch article")).map(function (article, index) {
      var title = article.querySelector("h3");
      var description = article.querySelector("p");
      return {
        number: String(index + 1).padStart(2, "0"),
        title: title ? title.textContent.trim() : "",
        text: description ? description.textContent.trim() : ""
      };
    }).filter(function (item) { return item.title && item.text; });
    if (!heading || !cards.length) return;

    var canonical = document.querySelector('link[rel="canonical"]');
    var pageUrl = canonical && canonical.href ? canonical.href : location.origin + location.pathname;
    var shareUrl = pageUrl.split("#")[0] + "#watch";
    var title = document.title.split("|")[0].trim();
    var weekMatch = (title + " " + heading.textContent).match(/week\s*0?(\d+)/i);
    var week = weekMatch ? String(weekMatch[1]).padStart(2, "0") : "00";
    var opponent = title.match(/vs\.?\s+(.+?)(?:\s*[:|]|$)/i);
    var matchup = opponent ? "SEATTLE VS " + opponent[1].trim().toUpperCase() : "SEATTLE GAME DAY";
    var prefix = "hawks-war-room-w" + week + "-watch";

    var actions = document.createElement("div");
    actions.className = "watch-export-actions";
    actions.setAttribute("aria-label", "Share or export the ten things to watch");
    actions.innerHTML = '<button type="button" class="watch-export-primary" data-watch-graphics>Export 5 social graphics</button>' +
      '<button type="button" data-watch-share>Share section</button>' +
      '<button type="button" data-watch-copy>Copy all ' + cards.length + '</button>';
    heading.insertAdjacentElement("afterend", actions);

    var feedback = document.createElement("p");
    feedback.className = "watch-export-feedback";
    feedback.setAttribute("role", "status");
    feedback.setAttribute("aria-live", "polite");
    feedback.textContent = "";
    actions.insertAdjacentElement("afterend", feedback);

    var dialog = document.createElement("dialog");
    dialog.className = "watch-export-dialog";
    dialog.setAttribute("aria-label", "Export social graphics");
    dialog.innerHTML = '<div class="watch-exp-top"><div><span class="watch-exp-kicker">HAWKS WAR ROOM / SHARE KIT</span>' +
      '<h2>Ten Things, Five Graphics</h2>' +
      '<p>Two scouting calls per card. Save them for a post, share an image, or grab all five in one ZIP.</p></div>' +
      '<button type="button" class="watch-exp-close" data-exp-close aria-label="Close export window">Close</button></div>' +
      '<div class="watch-exp-body"><div class="watch-exp-toolbar">' +
      '<button type="button" class="watch-exp-btn watch-exp-primary" data-exp-all disabled>Download all 5 (.zip)</button>' +
      '<button type="button" class="watch-exp-btn" data-exp-share-all disabled>Share 5 images</button></div>' +
      '<p class="watch-exp-status" role="status" aria-live="polite">Preparing graphics...</p>' +
      '<div class="watch-exp-list"></div>' +
      '<p class="watch-exp-hint">1080 × 1350 PNGs, generated here from the current scouting cards. No logo or account required.</p></div>';
    document.body.appendChild(dialog);

    var exportButton = actions.querySelector("[data-watch-graphics]");
    var copyButton = actions.querySelector("[data-watch-copy]");
    var shareButton = actions.querySelector("[data-watch-share]");
    var allButton = dialog.querySelector("[data-exp-all]");
    var shareAllButton = dialog.querySelector("[data-exp-share-all]");
    var status = dialog.querySelector(".watch-exp-status");
    var list = dialog.querySelector(".watch-exp-list");
    var images = null;
    var preparing = null;

    function notify(text) { feedback.textContent = text; }
    function exportStatus(text) { status.textContent = text; }

    function formatText() {
      return title + "\n10 Things I'm Watching\n\n" +
        cards.map(function (card) {
          return parseInt(card.number, 10) + ". " + card.title + "\n" + card.text;
        }).join("\n\n") + "\n\nRead the section: " + shareUrl;
    }

    async function copyText(text) {
      if (navigator.clipboard && navigator.clipboard.writeText) {
        try { await navigator.clipboard.writeText(text); return true; } catch (error) {}
      }
      var field = document.createElement("textarea");
      field.value = text;
      field.setAttribute("readonly", "");
      field.style.cssText = "position:fixed;left:-9999px;top:0;opacity:0";
      document.body.appendChild(field);
      field.select();
      var success = false;
      try { success = document.execCommand("copy"); } catch (error) {}
      field.remove();
      return success;
    }

    copyButton.addEventListener("click", async function () {
      var text = formatText();
      if (await copyText(text)) notify("All " + cards.length + " scouting calls copied.");
      else { window.prompt("Copy the scouting calls:", text); notify("Select the text in the box to copy it."); }
    });

    shareButton.addEventListener("click", async function () {
      var message = "My " + cards.length + " things to watch this week. " + shareUrl;
      if (navigator.share) {
        try {
          await navigator.share({ title: title + " | Hawks War Room", text: message, url: shareUrl });
          notify("Shared the section link.");
          return;
        } catch (error) {
          if (error && error.name === "AbortError") return;
        }
      }
      if (await copyText(shareUrl)) notify("Direct link to the ten things copied.");
      else { window.prompt("Copy the section link:", shareUrl); notify("Copy the link in the box."); }
    });

    function rounded(ctx, x, y, width, height, radius) {
      var r = Math.min(radius, width / 2, height / 2);
      ctx.beginPath();
      ctx.moveTo(x + r, y);
      ctx.lineTo(x + width - r, y);
      ctx.quadraticCurveTo(x + width, y, x + width, y + r);
      ctx.lineTo(x + width, y + height - r);
      ctx.quadraticCurveTo(x + width, y + height, x + width - r, y + height);
      ctx.lineTo(x + r, y + height);
      ctx.quadraticCurveTo(x, y + height, x, y + height - r);
      ctx.lineTo(x, y + r);
      ctx.quadraticCurveTo(x, y, x + r, y);
      ctx.closePath();
    }

    function wrap(ctx, text, maxWidth) {
      var words = String(text).split(/\s+/);
      var lines = [];
      var current = "";
      words.forEach(function (word) {
        var test = current ? current + " " + word : word;
        if (current && ctx.measureText(test).width > maxWidth) {
          lines.push(current);
          current = word;
        } else current = test;
      });
      if (current) lines.push(current);
      return lines;
    }

    function drawTextLines(ctx, lines, x, top, lineHeight) {
      lines.forEach(function (line, index) {
        ctx.fillText(line, x, top + index * lineHeight);
      });
    }

    function drawCard(ctx, card, x, y, width, height) {
      rounded(ctx, x, y, width, height, 20);
      ctx.fillStyle = "#172a3d";
      ctx.fill();
      ctx.strokeStyle = "#39536b";
      ctx.lineWidth = 2;
      ctx.stroke();
      ctx.fillStyle = "#c9ff3d";
      ctx.fillRect(x + 30, y + 40, 5, 70);
      ctx.textAlign = "left";
      ctx.textBaseline = "top";
      ctx.font = '72px Anton, Impact, sans-serif';
      ctx.fillText(card.number, x + 46, y + 34);

      var titleSize = 47;
      var titleLines = [];
      do {
        ctx.font = titleSize + 'px Anton, Impact, sans-serif';
        titleLines = wrap(ctx, card.title.toUpperCase(), width - 185);
        if (titleLines.length <= 2 || titleSize <= 31) break;
        titleSize -= 2;
      } while (true);
      ctx.fillStyle = "#f4f7fc";
      drawTextLines(ctx, titleLines, x + 154, y + 47, titleSize * 1.16);

      var bodyTop = y + 145 + Math.max(0, titleLines.length - 1) * 47;
      var remaining = y + height - 31 - bodyTop;
      var bodySize = 32;
      var bodyLines = [];
      var bodyStep = 0;
      do {
        ctx.font = '500 ' + bodySize + 'px Barlow, Arial, sans-serif';
        bodyLines = wrap(ctx, card.text, width - 86);
        bodyStep = bodySize * 1.34;
        if (bodyLines.length * bodyStep <= remaining || bodySize <= 19) break;
        bodySize -= 1;
      } while (true);
      ctx.fillStyle = "#d1deeb";
      ctx.save();
      ctx.beginPath();
      ctx.rect(x + 42, bodyTop, width - 84, remaining + 7);
      ctx.clip();
      drawTextLines(ctx, bodyLines, x + 42, bodyTop, bodyStep);
      ctx.restore();
    }

    function makePicture(left, right, index, total) {
      var canvas = document.createElement("canvas");
      canvas.width = 1080;
      canvas.height = 1350;
      var ctx = canvas.getContext("2d", { alpha: false });
      if (!ctx) throw new Error("Canvas is unavailable in this browser.");
      var gradient = ctx.createLinearGradient(0, 0, 1080, 1350);
      gradient.addColorStop(0, "#0d2335");
      gradient.addColorStop(.6, "#081523");
      gradient.addColorStop(1, "#0a1220");
      ctx.fillStyle = gradient;
      ctx.fillRect(0, 0, 1080, 1350);

      ctx.fillStyle = "rgba(201,255,61,.07)";
      ctx.beginPath();
      ctx.arc(1090, 10, 400, 0, Math.PI * 2);
      ctx.fill();
      ctx.fillStyle = "#c9ff3d";
      ctx.fillRect(62, 65, 9, 72);
      ctx.textBaseline = "top";
      ctx.textAlign = "left";
      ctx.font = '700 26px "IBM Plex Mono", monospace';
      ctx.fillText("HAWKS WAR ROOM", 95, 70);
      ctx.fillStyle = "#b7c9d9";
      ctx.font = '500 23px "IBM Plex Mono", monospace';
      ctx.textAlign = "right";
      ctx.fillText("WEEK " + week + " / 2026", 1016, 74);
      ctx.textAlign = "left";
      ctx.font = '100px Anton, Impact, sans-serif';
      ctx.fillStyle = "#f2f6fc";
      ctx.fillText("10 THINGS TO WATCH", 62, 132);
      ctx.font = '600 23px "IBM Plex Mono", monospace';
      ctx.fillStyle = "#c9ff3d";
      ctx.fillText(matchup, 65, 251);
      ctx.fillStyle = "#294154";
      ctx.fillRect(62, 298, 956, 2);

      drawCard(ctx, left, 62, 332, 956, 420);
      drawCard(ctx, right, 62, 774, 956, 420);

      ctx.fillStyle = "#c9ff3d";
      ctx.fillRect(62, 1231, 105, 4);
      ctx.fillStyle = "#f2f6fc";
      ctx.font = '700 25px "IBM Plex Mono", monospace';
      ctx.fillText("HAWKSWARROOM.COM", 62, 1255);
      ctx.textAlign = "right";
      ctx.fillStyle = "#b6c6d9";
      ctx.font = '600 22px "IBM Plex Mono", monospace';
      ctx.fillText(String(index + 1).padStart(2, "0") + " / " + String(total).padStart(2, "0"), 1016, 1256);
      ctx.textAlign = "left";
      ctx.fillStyle = "#8ca0b5";
      ctx.font = '500 19px Barlow, Arial, sans-serif';
      ctx.fillText("Independent fan project. Not affiliated with the Seahawks or NFL.", 62, 1300);
      return new Promise(function (resolve, reject) {
        canvas.toBlob(function (blob) {
          if (blob) resolve(blob);
          else reject(new Error("The browser could not render the PNG."));
        }, "image/png");
      });
    }

    function download(blob, filename) {
      var url = URL.createObjectURL(blob);
      var link = document.createElement("a");
      link.href = url;
      link.download = filename;
      link.style.display = "none";
      document.body.appendChild(link);
      link.click();
      link.remove();
      setTimeout(function () { URL.revokeObjectURL(url); }, 60000);
    }

    function crc32(bytes) {
      var crc = 0xFFFFFFFF;
      for (var i = 0; i < bytes.length; i++) {
        crc ^= bytes[i];
        for (var j = 0; j < 8; j++) {
          crc = (crc >>> 1) ^ ((crc & 1) ? 0xEDB88320 : 0);
        }
      }
      return (crc ^ 0xFFFFFFFF) >>> 0;
    }

    async function zipPictures(items) {
      var locals = [];
      var central = [];
      var encoder = new TextEncoder();
      var offset = 0;
      var centralSize = 0;
      for (var i = 0; i < items.length; i++) {
        var entry = items[i];
        var bytes = new Uint8Array(await entry.blob.arrayBuffer());
        var nameBytes = encoder.encode(entry.name);
        var crc = crc32(bytes);
        var local = new Uint8Array(30 + nameBytes.length);
        var l = new DataView(local.buffer);
        l.setUint32(0, 0x04034b50, true);
        l.setUint16(4, 20, true);
        l.setUint32(14, crc, true);
        l.setUint32(18, bytes.length, true);
        l.setUint32(22, bytes.length, true);
        l.setUint16(26, nameBytes.length, true);
        local.set(nameBytes, 30);
        locals.push(local, bytes);

        var center = new Uint8Array(46 + nameBytes.length);
        var c = new DataView(center.buffer);
        c.setUint32(0, 0x02014b50, true);
        c.setUint16(4, 20, true);
        c.setUint16(6, 20, true);
        c.setUint32(16, crc, true);
        c.setUint32(20, bytes.length, true);
        c.setUint32(24, bytes.length, true);
        c.setUint16(28, nameBytes.length, true);
        c.setUint32(42, offset, true);
        center.set(nameBytes, 46);
        central.push(center);
        centralSize += center.length;
        offset += local.length + bytes.length;
      }
      var end = new Uint8Array(22);
      var e = new DataView(end.buffer);
      e.setUint32(0, 0x06054b50, true);
      e.setUint16(8, items.length, true);
      e.setUint16(10, items.length, true);
      e.setUint32(12, centralSize, true);
      e.setUint32(16, offset, true);
      return new Blob(locals.concat(central, [end]), { type: "application/zip" });
    }

    function renderImages() {
      list.textContent = "";
      images.forEach(function (item, index) {
        var card = document.createElement("div");
        card.className = "watch-exp-card";
        var preview = document.createElement("img");
        preview.src = item.url;
        preview.alt = "Graphic " + (index + 1) + " of " + images.length + ", scouting calls " + (index * 2 + 1) + " and " + Math.min(index * 2 + 2, cards.length);
        preview.loading = "lazy";
        var foot = document.createElement("div");
        foot.className = "watch-exp-card-foot";
        var label = document.createElement("span");
        label.textContent = "CALLS " + String(index * 2 + 1).padStart(2, "0") + "-" + String(Math.min(index * 2 + 2, cards.length)).padStart(2, "0");
        var button = document.createElement("button");
        button.className = "watch-exp-btn";
        button.type = "button";
        button.textContent = "Save PNG";
        button.addEventListener("click", function () { download(item.blob, item.name); });
        foot.appendChild(label);
        foot.appendChild(button);
        card.appendChild(preview);
        card.appendChild(foot);
        list.appendChild(card);
      });
      allButton.disabled = false;
      shareAllButton.disabled = false;
      allButton.textContent = "Download all " + images.length + " (.zip)";
      shareAllButton.textContent = "Share " + images.length + " images";
      exportStatus("Ready. " + images.length + " images, 1080 × 1350 pixels each.");
    }

    async function prepare() {
      if (images) return;
      if (preparing) return preparing;
      preparing = (async function () {
        if (document.fonts && document.fonts.ready) await document.fonts.ready;
        var output = [];
        var total = Math.ceil(cards.length / 2);
        for (var i = 0; i < total; i++) {
          exportStatus("Creating graphic " + (i + 1) + " of " + total + "...");
          var left = cards[i * 2];
          var right = cards[i * 2 + 1] || { number: "", title: "", text: "" };
          var blob = await makePicture(left, right, i, total);
          var first = String(i * 2 + 1).padStart(2, "0");
          var last = String(Math.min(cards.length, i * 2 + 2)).padStart(2, "0");
          var name = prefix + "-" + first + "-" + last + ".png";
          output.push({ blob: blob, name: name, url: URL.createObjectURL(blob) });
        }
        images = output;
        renderImages();
      })();
      try { await preparing; }
      catch (error) {
        exportStatus("Export failed: " + (error && error.message ? error.message : "Unknown error"));
      }
      finally { preparing = null; }
    }

    function openDialog() {
      if (typeof dialog.showModal === "function") dialog.showModal();
      else dialog.setAttribute("open", "");
      prepare();
    }
    function closeDialog() {
      if (typeof dialog.close === "function") dialog.close();
      else dialog.removeAttribute("open");
      exportButton.focus();
    }
    exportButton.addEventListener("click", openDialog);
    dialog.querySelector("[data-exp-close]").addEventListener("click", closeDialog);
    dialog.addEventListener("click", function (event) {
      if (event.target === dialog) closeDialog();
    });

    allButton.addEventListener("click", async function () {
      if (!images) return;
      allButton.disabled = true;
      exportStatus("Packing " + images.length + " images into one ZIP...");
      try {
        var zip = await zipPictures(images);
        download(zip, prefix + "-all-" + images.length + ".zip");
        exportStatus("ZIP downloaded with " + images.length + " PNGs.");
      } catch (error) {
        exportStatus("ZIP export failed. You can save each PNG below.");
      } finally {
        allButton.disabled = false;
      }
    });

    shareAllButton.addEventListener("click", async function () {
      if (!images) return;
      var files = images.map(function (item) {
        return new File([item.blob], item.name, { type: "image/png" });
      });
      if (navigator.share && navigator.canShare && navigator.canShare({ files: files })) {
        try {
          await navigator.share({ files: files, title: title + " | Hawks War Room", text: "My things to watch against Arizona. " + shareUrl });
          exportStatus("Images sent to your share sheet.");
          return;
        } catch (error) {
          if (error && error.name === "AbortError") return;
        }
      }
      exportStatus("Image sharing is unavailable here. Use Download all 5 (.zip) or save individual PNGs.");
    });
  }

  if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", boot);
  else boot();
})();