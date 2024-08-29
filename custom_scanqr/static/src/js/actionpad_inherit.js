/** @odoo-module **/

import { patch } from "@web/core/utils/patch";
import { ActionpadWidget } from "@point_of_sale/app/screens/product_screen/action_pad/action_pad";
const jsQR = window.jsQR;
import { useService } from "@web/core/utils/hooks";
import { loadImage } from "@point_of_sale/utils";
import { getDataURLFromFile } from "@web/core/utils/urls";

document.addEventListener("DOMContentLoaded", () => {
    if (!document.getElementById("file_camera_modal")) {
        const modalTemplate = `
            <div id="file_camera_modal" class="modal" style="display: none;">
                <div class="modal-dialog">
                    <div class="modal-content">
                        <div class="modal-header">
                            <h5 class="modal-title">Scan QR Code</h5>
                            <button type="button" class="close" aria-label="Close">
                                <span aria-hidden="true">&times;</span>
                            </button>
                        </div>
                        <div class="modal-body">
                            <button id="camera_button" class="btn btn-primary mb-3">Open Camera</button>
                            <button id="load_button" class="btn btn-secondary mb-3">Load File</button>
                            <input type="file" id="file_input" class="image-uploader form-control mb-3" />
                            <video id="camera_preview" autoplay playsinline style="display:none;"></video>
                            <canvas id="captured_canvas" style="display:none;"></canvas>
                            <button id="check_qr_button" class="btn btn-secondary" style="display:none;">Check QR Code</button>
                        </div>
                    </div>
                </div>
            </div>
        `;
        document.body.insertAdjacentHTML('beforeend', modalTemplate);
    }

    let textData = null;
    let customerData = null;

    patch(ActionpadWidget.prototype, {
        setup() {
            super.setup();
            this.orm = useService("orm"); // Properly initialize the ORM service
        },

        async onClick() {
            // Show the modal with options
            const modal = document.getElementById("file_camera_modal");
            modal.style.display = "block";

            document.getElementById('camera_button').addEventListener('click', async () => {
                // Handle camera functionality
                await this._initializeCamera();
            });

            document.getElementById('load_button').addEventListener('click', () => {
                // Trigger file input click
                document.getElementById('file_input').click();
            });

            document.getElementById('file_input').addEventListener('change', (event) => {
                const file = event.target.files[0];
                if (file) {
                    const reader = new FileReader();
                    reader.onload = async (e) => {
                        const img = new Image();
                        img.onload = async () => {
                            const canvas = document.getElementById('captured_canvas');
                            const context = canvas.getContext('2d');
                            // Resize image to 100x100 pixels
                            const fixedWidth = 500;
                            const fixedHeight = 500;
                            await this._resizeImage(img, fixedWidth, fixedHeight, canvas, context);
                            canvas.style.display = 'block';
                            document.getElementById('check_qr_button').style.display = 'inline-block';
                            document.getElementById('camera_preview').style.display = 'none';
                        };
                        img.src = e.target.result;
                    };
                    reader.readAsDataURL(file);
                }
            });

            document.getElementById('check_qr_button').addEventListener('click', async () => {
                await this._scanForQRCodeAndFindCustomer();
            });

            document.querySelector("#file_camera_modal .close").addEventListener("click", () => {
                this._closeCanvasAndModal();
            });
        },

        async _initializeCamera() {
            const devices = await this._getVideoDevices();
            if (devices.length > 0) {
                const deviceId = devices[0].deviceId; // Select the first available camera
                const stream = await this._requestCameraAccess(deviceId);
                if (stream) {
                    this._startCameraPreview(stream);
                }
            } else {
                alert("No camera devices found.");
            }
        },

        async _getVideoDevices() {
            try {
                const devices = await navigator.mediaDevices.enumerateDevices();
                return devices.filter(device => device.kind === 'videoinput');
            } catch (error) {
                console.error("Error enumerating devices: ", error);
                return [];
            }
        },

        async _requestCameraAccess(deviceId) {
            try {
                const stream = await navigator.mediaDevices.getUserMedia({
                    video: {
                        deviceId: deviceId ? { exact: deviceId } : undefined,
                        facingMode: "environment",
                    },
                    audio: false,
                });
                return stream;
            } catch (error) {
                console.error("Camera access denied or an error occurred: ", error);
                return null;
            }
        },

        _startCameraPreview(stream) {
            const modal = document.getElementById("file_camera_modal");
            const videoElement = document.getElementById("camera_preview");

            modal.style.display = "block";
            videoElement.srcObject = stream;
            videoElement.setAttribute("playsinline", true);
            videoElement.style.display = 'block';
            videoElement.play();

            const captureButton = document.getElementById("capture_button");
            if (!captureButton) {
                const newCaptureButton = document.createElement('button');
                newCaptureButton.id = "capture_button";
                newCaptureButton.className = "btn btn-primary";
                newCaptureButton.innerText = "Capture Image";
                modal.querySelector(".modal-body").appendChild(newCaptureButton);

                newCaptureButton.addEventListener("click", () => {
                    this._captureImage(videoElement, stream);
                });
            }

            document.getElementById('check_qr_button').style.display = 'none';
        },

        _captureImage(videoElement, stream) {
            const canvasElement = document.getElementById("captured_canvas");
            const canvas = canvasElement.getContext("2d");

            canvasElement.height = 500; // Fixed height
            canvasElement.width = 500;  // Fixed width

            canvas.drawImage(videoElement, 0, 0, canvasElement.width, canvasElement.height);

            stream.getTracks().forEach(track => track.stop());

            canvasElement.style.display = "block";
            document.getElementById("check_qr_button").style.display = "inline-block";
            videoElement.style.display = "none";
        },

        async _scanForQRCodeAndFindCustomer() {
            const canvasElement = document.getElementById("captured_canvas");
            const canvas = canvasElement.getContext("2d");

            const imageData = canvas.getImageData(0, 0, canvasElement.width, canvasElement.height);

            if (typeof jsQR === 'function') {
                const qrCode = jsQR(imageData.data, imageData.width, imageData.height);
                if (qrCode && qrCode.data) {
                    textData = qrCode.data;
                    await this._findCustomer();
                } else {
                    alert("No QR code found in the captured image.");
                    location.reload(); // Refresh the page if no QR code is found
                }
            } else {
                console.error("jsQR is not recognized as a function. Ensure it is loaded correctly.");
            }
        },

        async uploadImage(event) {
            const file = event.target.files[0];
            if (!file.type.match(/image.*/)) {
                await this.popup.add(ErrorPopup, {
                    title: _t("Unsupported File Format"),
                    body: _t("Only web-compatible Image formats such as .png or .jpeg are supported."),
                });
            } else {
                const imageUrl = await getDataURLFromFile(file);
                const loadedImage = await loadImage(imageUrl, {
                    onError: () => {
                        this.popup.add(ErrorPopup, {
                            title: _t("Loading Image Error"),
                            body: _t("Encountered error when loading image. Please try again."),
                        });
                    }
                });
                console.log('loadedImage-----------',loadedImage, this.changes)
                if (loadedImage) {
                    const canvas = document.getElementById('captured_canvas');
                    const context = canvas.getContext('2d');
                    const fixedWidth = 500;
                    const fixedHeight = 500;
                    await this._resizeImage(loadedImage, fixedWidth, fixedHeight, canvas, context);
                    this.changes.image_1920 = canvas.toDataURL();
                }
            }
        },

        _resizeImage(img, fixedWidth, fixedHeight, canvas, context) {
            canvas.width = fixedWidth;
            canvas.height = fixedHeight;

            context.drawImage(img, 0, 0, fixedWidth, fixedHeight);
            return canvas;
        },

        async _findCustomer() {
            if (!textData) {
                console.error("No text data available to find the customer.");
                return;
            }

            try {
                const domain = [['phone', '=', textData]];
                const fields = ['name', 'phone', 'id'];

                const response = await this.orm.call('res.partner', 'search_read', [domain, fields]);

                if (response && response.length > 0) {
                    customerData = response[0];
                    this.pos.get_order().set_partner(customerData);
                    this._closeCanvasAndModal();
                    this._displayCustomerData(customerData);
                } else {
                    alert("No customer found with the given data.");
                }
            } catch (error) {
                console.error("Error finding customer:", error);
                alert("An error occurred while trying to find the customer.");
            }
        },

        _closeCanvasAndModal() {
            const modal = document.getElementById("file_camera_modal");
            const canvasElement = document.getElementById("captured_canvas");

            if (canvasElement) {
                canvasElement.style.display = "none";
            }

            if (modal) {
                modal.style.display = "none";
            }

            const videoElement = document.getElementById("camera_preview");
            if (videoElement && videoElement.srcObject) {
                videoElement.srcObject.getTracks().forEach(track => track.stop());
            }
        },

        _displayCustomerData(customer) {
            if (customer) {
                console.log(`Customer found: ${customer.name} (${customer.phone})`);
            } else {
                alert("No customer data available.");
            }
        },
    });
});
