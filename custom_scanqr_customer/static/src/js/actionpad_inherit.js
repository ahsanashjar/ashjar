/** @odoo-module **/
import { patch } from "@web/core/utils/patch";
import { ActionpadWidget } from "@point_of_sale/app/screens/product_screen/action_pad/action_pad";
import { useService } from "@web/core/utils/hooks";

// Ensure jsQR is included
const jsQR = window.jsQR;

document.addEventListener("DOMContentLoaded", () => {
    // Ensure the modal template is only added once
    if (!document.getElementById("file_camera_modal")) {
        const modalTemplate = `
            <div id="file_camera_modal" class="modal" style="display: none;">
                <div class="modal-dialog">
                    <div class="modal-content">
                        <div class="modal-header">
                            <h5 class="modal-title">Scan Barcode/QR Code</h5>
                            <button type="button" class="close" aria-label="Close">
                                <span aria-hidden="true">&times;</span>
                            </button>
                        </div>
                        <div class="modal-body">
                            <div id="scanner_container" style="position:relative; width:100%; height:400px;">
                                <!-- Camera Preview -->
                                <video id="camera_preview" style="width:100%; height:100%; opacity: 0.8;" autoplay playsinline></video>
                                <!-- Scanner Canvas -->
                                <canvas id="camera_canvas" style="position:absolute; top:0; left:0; width:100%; height:100%;"></canvas>
                            </div>
                            <span id="capture_image">Auto Capture</span>
                        </div>
                    </div>
                </div>
            </div>
        `;
        document.body.insertAdjacentHTML('beforeend', modalTemplate);
    }

    patch(ActionpadWidget.prototype, {
        setup() {
            super.setup();
            this.orm = useService("orm");
            this.notification = useService("notification");
        },

        async onClick() {
            const modal = document.getElementById("file_camera_modal");
            modal.style.display = "block";

            this._initializeLiveScanner();

            document.querySelector("#file_camera_modal .close").addEventListener("click", () => {
                this._stopLiveScanner();
                modal.style.display = "none";
            });

            document.getElementById("capture_image").addEventListener("click", () => {
                this._captureImage();
            });
        },

        _initializeLiveScanner() {
            const videoElement = document.querySelector('#camera_preview');
            const canvasElement = document.querySelector('#camera_canvas');
            const canvasContext = canvasElement.getContext('2d');

            if (!videoElement || !canvasElement || !canvasContext) {
                console.error("Required elements for the scanner are not found.");
                return;
            }

            if (navigator.mediaDevices && navigator.mediaDevices.getUserMedia) {
                navigator.mediaDevices.getUserMedia({
                    video: {
                        facingMode: "environment",
                        width: { ideal: 1280 },
                        height: { ideal: 720 }
                    }
                }).then((stream) => {
                    videoElement.srcObject = stream;
                    videoElement.setAttribute("playsinline", true);
                    videoElement.play();
                    this._scanQRCode(videoElement, canvasElement, canvasContext);
                }).catch((error) => {
                    console.error("Error accessing camera:", error);
                    alert("Unable to access the camera. Please check your permissions or try a different browser.");
                });
            } else {
                alert("Your browser does not support camera access. Please try a different browser.");
            }
        },

        _scanQRCode(video, canvas, context) {
            const scan = () => {
                if (video.readyState === video.HAVE_ENOUGH_DATA) {
                    canvas.height = video.videoHeight;
                    canvas.width = video.videoWidth;
                    context.drawImage(video, 0, 0, canvas.width, canvas.height);
                    const imageData = context.getImageData(0, 0, canvas.width, canvas.height);
                    const code = jsQR(imageData.data, canvas.width, canvas.height, {
                        inversionAttempts: "dontInvert",
                    });
                    if (code) {
                        this._processQRCode(code.data);
                        this._stopLiveScanner();
                        document.getElementById("file_camera_modal").style.display = "none";
                    }
                }
                requestAnimationFrame(scan);
            };
            scan();
        },

        _stopLiveScanner() {
            const videoElement = document.querySelector('#camera_preview');
            if (videoElement && videoElement.srcObject) {
                const stream = videoElement.srcObject;
                const tracks = stream.getTracks();
                tracks.forEach((track) => track.stop());
                videoElement.srcObject = null;
            }
        },

        async _processQRCode(code) {
            if (!code) {
                console.error("No code available for processing.");
                return;
            }

            try {
                const domain = [['phone', '=', code]];
                const fields = ['name', 'phone', 'id'];

                const response = await this.orm.call('res.partner', 'search_read', [domain, fields]);

                if (response && response.length > 0) {
                    const customerData = response[0];
                    if (customerData) {
                        this.pos.get_order().set_partner(customerData);
                        this._displayCustomerData(customerData);

                        // Push a green notification for a successful match
                        this.notification.add("Customer found and set: " + customerData.name, {
                            type: 'success',
                            sticky: false, // Notification will disappear after some time
                        });
                    } else {
                        this._pushNotification("Customer data is null or undefined.", 'danger');
                    }
                } else {
                    this._pushNotification("No customer found with the scanned code.", 'danger');
                }
            } catch (error) {
                console.error("Error processing QR code:", error);
                this._pushNotification("Customer Selected.", 'success');
            }
        },

        _displayCustomerData(customer) {
            if (customer) {
                console.log(`Customer found: ${customer.name} (${customer.phone})`);
            } else {
                this._pushNotification("No customer data available.", 'danger');
            }
        },

        _captureImage() {
            const canvasElement = document.querySelector('#camera_canvas');
            const context = canvasElement.getContext('2d');
            const videoElement = document.querySelector('#camera_preview');

            if (videoElement && canvasElement && context) {
                canvasElement.height = videoElement.videoHeight;
                canvasElement.width = videoElement.videoWidth;
                context.drawImage(videoElement, 0, 0, canvasElement.width, canvasElement.height);
                const imageData = context.getImageData(0, 0, canvasElement.width, canvasElement.height);
                const code = jsQR(imageData.data, canvasElement.width, canvasElement.height, {
                    inversionAttempts: "dontInvert",
                });
                if (code) {
                    this._processQRCode(code.data);
                    this._stopLiveScanner();
                    document.getElementById("file_camera_modal").style.display = "none";
                } else {
                    this._pushNotification("No QR code found in the image.", 'danger');
                }
            } else {
                this._pushNotification("Error capturing image. Please try again.", 'danger');
            }
        },

        _pushNotification(message, type) {
            this.notification.add(message, {
                type: type === 'success' ? 'success' : 'danger',
                sticky: false,
            });
        }
    });
});
