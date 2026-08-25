define([], function() {
    function supportedType() {
        var candidates = ['audio/webm;codecs=opus', 'audio/ogg;codecs=opus', 'audio/webm'];
        for (var i = 0; i < candidates.length; i += 1) {
            if (window.MediaRecorder && MediaRecorder.isTypeSupported(candidates[i])) {
                return candidates[i];
            }
        }
        return '';
    }

    function uuid() {
        if (window.crypto && window.crypto.randomUUID) {
            return window.crypto.randomUUID();
        }
        return String(Date.now()) + '-' + Math.random().toString(16).slice(2);
    }

    function initOne(root) {
        if (!root || root.dataset.tuneaiRecorderReady === '1') {
            return;
        }
        root.dataset.tuneaiRecorderReady = '1';
        var start = root.querySelector('.local-tuneai-start');
        var stop = root.querySelector('.local-tuneai-stop');
        var submit = root.querySelector('.local-tuneai-submit');
        var status = root.querySelector('.local-tuneai-status');
        var chunks = [];
        var recorder = null;
        var recorded = null;
        var submissionId = null;
        var attemptId = null;

        function setStatus(text) {
            status.textContent = text;
        }

        start.addEventListener('click', function() {
            if (!navigator.mediaDevices || !navigator.mediaDevices.getUserMedia) {
                setStatus('Browser does not support microphone recording.');
                return;
            }
            navigator.mediaDevices.getUserMedia({audio: true}).then(function(stream) {
                chunks = [];
                recorded = null;
                submissionId = uuid();
                attemptId = uuid();
                var type = supportedType();
                recorder = new MediaRecorder(stream, type ? {mimeType: type} : undefined);
                recorder.ondataavailable = function(event) {
                    if (event.data.size > 0) {
                        chunks.push(event.data);
                    }
                };
                recorder.onstop = function() {
                    recorded = new Blob(chunks, {type: recorder.mimeType || 'audio/webm'});
                    stream.getTracks().forEach(function(track) {
                        track.stop();
                    });
                    start.disabled = false;
                    stop.disabled = true;
                    submit.disabled = false;
                    setStatus('Recording is ready to submit.');
                };
                recorder.start();
                start.disabled = true;
                stop.disabled = false;
                submit.disabled = true;
                setStatus('Recording...');
            }).catch(function() {
                setStatus('Microphone permission was denied.');
            });
        });

        stop.addEventListener('click', function() {
            if (recorder && recorder.state === 'recording') {
                recorder.stop();
            }
        });

        submit.addEventListener('click', function() {
            if (!recorded) {
                setStatus('Record audio before submitting.');
                return;
            }
            var form = new FormData();
            form.append('sesskey', root.dataset.sesskey);
            form.append('courseid', root.dataset.courseid);
            form.append('cmid', root.dataset.cmid);
            form.append('questionid', root.dataset.questionid);
            if (root.dataset.groupid) {
                form.append('groupid', root.dataset.groupid);
            }
            form.append('external_submission_id', submissionId);
            form.append('external_attempt_id', attemptId);
            form.append('audio', recorded, 'answer.webm');
            submit.disabled = true;
            root.setAttribute('aria-busy', 'true');
            setStatus('Submitting...');
            fetch(root.dataset.endpoint, {
                method: 'POST',
                body: form,
                credentials: 'same-origin'
            }).then(function(response) {
                return response.json().then(function(payload) {
                    if (!response.ok || !payload.ok) {
                        throw new Error(payload.error || 'TuneAI upload failed.');
                    }
                    setStatus('Submitted to TuneAI.');
                    root.setAttribute('aria-busy', 'false');
                    if (root.dataset.resulturl) {
                        window.location.assign(root.dataset.resulturl + '&external_submission_id=' + encodeURIComponent(submissionId));
                    }
                });
            }).catch(function(error) {
                submit.disabled = false;
                root.setAttribute('aria-busy', 'false');
                setStatus(error.message);
            });
        });
    }

    function init(selector) {
        var roots = document.querySelectorAll(selector);
        for (var i = 0; i < roots.length; i += 1) {
            initOne(roots[i]);
        }
    }

    return {
        init: init
    };
});
