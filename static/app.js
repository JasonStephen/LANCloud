const modal = document.getElementById('modal');
const openUpload = document.getElementById('openUpload');
const closeModal = document.getElementById('closeModal');
const drop = document.getElementById('drop');
const fileInput = document.getElementById('fileInput');
const doUpload = document.getElementById('doUpload');
const expiry = document.getElementById('expiry');
const statusEl = document.getElementById('status');

let selectedFiles = [];

openUpload?.addEventListener('click', () => modal.classList.remove('hidden'));
closeModal?.addEventListener('click', () => {
  modal.classList.add('hidden');
  selectedFiles = [];
  statusEl.textContent = '';
});

drop.addEventListener('click', () => fileInput.click());

drop.addEventListener('dragover', e => { e.preventDefault(); drop.classList.add('hover'); });
drop.addEventListener('dragleave', () => drop.classList.remove('hover'));
drop.addEventListener('drop', e => {
  e.preventDefault();
  drop.classList.remove('hover');
  selectedFiles = Array.from(e.dataTransfer.files);
  statusEl.textContent = `${selectedFiles.length} file(s) selected`;
});

fileInput.addEventListener('change', () => {
  selectedFiles = Array.from(fileInput.files);
  statusEl.textContent = `${selectedFiles.length} file(s) selected`;
});

doUpload.addEventListener('click', () => {

  if (!selectedFiles.length) {
    statusEl.textContent = 'Please select files first.';
    return;
  }

  statusEl.textContent = 'Preparing...';

  const form = new FormData();

  for (const f of selectedFiles) {
    form.append('files', f);
  }

  form.append('expiry', expiry.value);


  const xhr = new XMLHttpRequest();

  xhr.open('POST', '/upload');


  // ===== 上传进度监听 =====
  xhr.upload.onprogress = (e) => {

    if (e.lengthComputable) {

      const percent = Math.round(e.loaded / e.total * 100);

      statusEl.textContent = `Uploading... ${percent}%`;
    }
  };


  // ===== 完成 =====
  xhr.onload = () => {

    if (xhr.status === 200) {

      const res = JSON.parse(xhr.responseText);

      if (res.ok) {
        statusEl.textContent = `Done ✓ (${res.saved} files)`;
        setTimeout(() => location.reload(), 600);
      } else {
        statusEl.textContent = res.msg || 'Upload failed';
      }

    } else {
      statusEl.textContent = `Error (${xhr.status})`;
    }
  };


  // ===== 网络错误 =====
  xhr.onerror = () => {
    statusEl.textContent = 'Network error';
  };


  xhr.send(form);
});

// ===== Settings Panel =====

const openSettings = document.getElementById('openSettings');
const settingsModal = document.getElementById('settingsModal');
const closeSettings = document.getElementById('closeSettings');

const quotaSize = document.getElementById('quotaSize');
const quotaUnit = document.getElementById('quotaUnit');

const fileSize = document.getElementById('fileSize');
const fileUnit = document.getElementById('fileUnit');

const saveSettings = document.getElementById('saveSettings');
const settingsStatus = document.getElementById('settingsStatus');


// 打开设置窗口 → 拉当前配置
openSettings?.addEventListener('click', async () => {

  settingsModal.classList.remove('hidden');
  settingsStatus.textContent = 'Loading...';

  const res = await fetch('/settings/storage');
  const data = await res.json();

  // bytes → 单位换算显示
  if (data.quota_bytes >= 1024**3) {
    quotaSize.value = (data.quota_bytes / 1024**3).toFixed(1);
    quotaUnit.value = 'gb';
  } else {
    quotaSize.value = (data.quota_bytes / 1024**2).toFixed(0);
    quotaUnit.value = 'mb';
  }

  if (data.max_file_bytes >= 1024**3) {
    fileSize.value = (data.max_file_bytes / 1024**3).toFixed(1);
    fileUnit.value = 'gb';
  } else {
    fileSize.value = (data.max_file_bytes / 1024**2).toFixed(0);
    fileUnit.value = 'mb';
  }

  settingsStatus.textContent = '';
});


closeSettings?.addEventListener('click', () => {
  settingsModal.classList.add('hidden');
  settingsStatus.textContent = '';
});


// 保存设置
saveSettings?.addEventListener('click', async () => {

  settingsStatus.textContent = 'Saving...';

  const form = new FormData();

  form.append('quota_size', quotaSize.value);
  form.append('quota_unit', quotaUnit.value);

  form.append('file_size', fileSize.value);
  form.append('file_unit', fileUnit.value);


  const res = await fetch('/settings/storage', {
    method: 'POST',
    body: form
  });

  const data = await res.json();

  if (!res.ok || !data.ok) {
    settingsStatus.textContent = data.msg || 'Failed';
    return;
  }

  settingsStatus.textContent = 'Saved ✓';

  setTimeout(() => location.reload(), 800);
});

// ===== Delete file =====
document.querySelectorAll('.delBtn').forEach(btn => {
  btn.addEventListener('click', async () => {
    const id = btn.dataset.id;
    const ok = confirm('Delete this file? This cannot be undone.');
    if (!ok) return;

    btn.disabled = true;
    btn.textContent = 'Deleting...';

    const res = await fetch(`/files/${id}/delete`, { method: 'POST' });
    const data = await res.json().catch(() => ({}));

    if (!res.ok || !data.ok) {
      alert(data.msg || `Delete failed (${res.status})`);
      btn.disabled = false;
      btn.textContent = 'Delete';
      return;
    }

    // 最稳：直接刷新（也可以做 DOM 移除）
    location.reload();
  });
});