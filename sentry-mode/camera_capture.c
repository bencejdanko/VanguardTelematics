/*
 * Copyright (c) 2025, BlackBerry Limited. All rights reserved.
 *
 * Licensed under the Apache License, Version 2.0 (the "License");
 * you may not use this file except in compliance with the License.
 * You may obtain a copy of the License at
 *
 *     http://www.apache.org/licenses/LICENSE-2.0
 *
 * Unless required by applicable law or agreed to in writing, software
 * distributed under the License is distributed on an "AS IS" BASIS,
 * WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
 * See the License for the specific language governing permissions and
 * limitations under the License.
 */

#include <pthread.h>
#include <stdarg.h>
#include <stdio.h>
#include <stdlib.h>
#include <unistd.h>
#include <errno.h>
#include <stdbool.h>

#include <camera/camera_api.h>

#define GROUP_ID_STRING_LEN                 64
#define WINDOW_ID_MAX_SIZE                  64
#define MAX_STRING_LEGNTH                   80

static const char* DEFAULT_FILE_PATH =      "/tmp";

typedef enum {
    CLEANUP_NONE = 0,
    CLEANUP_MUTEX = 1 << 0,
    CLEANUP_VIEWFINDER = 1 << 1,
    CLEANUP_CAMERA_HANDLE = 1 << 2,
} cleanupFlags_t;

typedef enum {
    DUMP_NONE = 0,
    DUMP_RAW,
} dumpType_t;

typedef struct {
    char                filePath[MAX_STRING_LEGNTH];
    camera_frametype_t  frametype;
    pthread_mutex_t     mutex;
    dumpType_t          dumpType;
    int                 dumpRawCount;
} dumpFrameContext_t;

static int stopApp(camera_handle_t handle,
                   dumpFrameContext_t* dumpFrameContext,
                   uint32_t flags)
{
    int err;
    int rc = EOK;

    if ((flags & (uint32_t) CLEANUP_VIEWFINDER) != 0u) {
        err = camera_stop_viewfinder(handle);
        if (err != EOK) {
            (void) fprintf(stderr, "Failed to stop viewfinder: err=%d\n", err);
            rc = err;
        }
    }

    if ((flags & (uint32_t) CLEANUP_CAMERA_HANDLE) != 0u) {
        err = camera_close(handle);
        if (err != EOK) {
            (void) fprintf(stderr, "Failed to close handle: err=%d\n", err);
            rc = err;
        }
    }

    if ((flags & (uint32_t) CLEANUP_MUTEX) != 0u) {
        err = pthread_mutex_destroy(&dumpFrameContext->mutex);
        if (err != EOK) {
            (void) fprintf(stderr, "Failed to destroy mutex: err=%d\n", err);
            rc = err;
        }
    }

    return rc;
}

static int writeToDisk(const char* fileName, void* ptr, size_t size)
{
    FILE*   fptr;
    int     err;
    size_t  written;

    fptr = fopen(fileName, "w+b");
    if (fptr == NULL) {
        (void) fprintf(stderr, "Failed to open %s: err=%d\n", fileName, errno);
        return errno;
    }

    written = fwrite(ptr, size, 1, fptr);
    if (written < 1) {
        (void) fprintf(stderr, "Failed to write to disk %s: err=%d\n", fileName, errno);
        (void) fclose(fptr);
        return errno;
    }

    err = fclose(fptr);
    if (err == EOF) {
        (void) fprintf(stderr, "Failed to close file pointer: err=%d\n", errno);
        return errno;
    }

    return err;
}

int getBufferSize(camera_buffer_t buffer, camera_frametype_t frametype, size_t* size)
{
    int err = EOK;

    if (size == NULL) {
        (void) fprintf(stderr, "NULL parameter");
        return EINVAL;
    }

    switch((int)frametype) {
    case (int) CAMERA_FRAMETYPE_BGR8888:
        *size = buffer.framedesc.bgr8888.stride * buffer.framedesc.bgr8888.height;
        break;
    case (int) CAMERA_FRAMETYPE_RGB8888:
        *size = buffer.framedesc.rgb8888.stride * buffer.framedesc.rgb8888.height;
        break;
    case (int) CAMERA_FRAMETYPE_NV12:
        *size = buffer.framedesc.nv12.stride * buffer.framedesc.nv12.height;
        break;
    case (int) CAMERA_FRAMETYPE_YCBYCR:
        *size = buffer.framedesc.bgr8888.stride * buffer.framedesc.bgr8888.height;
        break;
    case (int) CAMERA_FRAMETYPE_CBYCRY:
        *size = buffer.framedesc.cbycry.stride * buffer.framedesc.cbycry.height;
        break;
    case (int) CAMERA_FRAMETYPE_RGB565:
        *size = buffer.framedesc.rgb565.stride * buffer.framedesc.rgb565.height;
        break;
    default:
        (void) fprintf(stderr, "Frametype %d is not supported\n", frametype);
        err = EINVAL;
        break;
    }

    return err;
}

static void dumpFrame(camera_handle_t handle, camera_buffer_t* buffer, void* arg)
{
    dumpFrameContext_t* context;
    dumpType_t          dumpType;
    int                 err;
    char                fileName[MAX_STRING_LEGNTH];
    size_t              bufferSize;

    if ((buffer == NULL) || (arg == NULL)) {
        (void) fprintf(stderr, "NULL argument in callback\n");
        return;
    }

    context = (dumpFrameContext_t*) arg;

    err = pthread_mutex_lock(&context->mutex);
    if (err != EOK) {
        (void) fprintf(stderr, "Failed to lock mutex: err=%d\n", err);
        return;
    }
    dumpType = context->dumpType;
    context->dumpType = DUMP_NONE;
    err = pthread_mutex_unlock(&context->mutex);
    if (err != EOK) {
        (void) fprintf(stderr, "Failed to unlock mutex: err=%d\n", err);
        return;
    }

    if (dumpType == DUMP_RAW) {
        err = snprintf(fileName,
                       sizeof(fileName),
                       "%s/frame%d.raw",
                       context->filePath,
                       context->dumpRawCount);
        if (err < 0) {
            (void) fprintf(stderr, "Failed to create a file name: err=%d\n", errno);
            return;
        }
        err = getBufferSize(*buffer, context->frametype, &bufferSize);
        if (err != EOK) {
            (void) fprintf(stderr, "Failed to get buffer size: err=%d\n", err);
            return;
        }
        err = writeToDisk(fileName, buffer->framebuf, bufferSize);
        if (err != EOK) {
            (void) fprintf(stderr, "Failed to dump a frame: err=%d\n", err);
        } else {
            // Determine dimensions based on format and output Meta string to stdout
            int width = 0, height = 0, stride = 0;
            switch ((int)context->frametype) {
                case (int) CAMERA_FRAMETYPE_BGR8888:
                    width = buffer->framedesc.bgr8888.width;
                    height = buffer->framedesc.bgr8888.height;
                    stride = buffer->framedesc.bgr8888.stride;
                    break;
                case (int) CAMERA_FRAMETYPE_RGB8888:
                    width = buffer->framedesc.rgb8888.width;
                    height = buffer->framedesc.rgb8888.height;
                    stride = buffer->framedesc.rgb8888.stride;
                    break;
                case (int) CAMERA_FRAMETYPE_NV12:
                    width = buffer->framedesc.nv12.width;
                    height = buffer->framedesc.nv12.height;
                    stride = buffer->framedesc.nv12.stride;
                    break;
                default:
                    width = buffer->framedesc.bgr8888.width;
                    height = buffer->framedesc.bgr8888.height;
                    stride = buffer->framedesc.bgr8888.stride;
                    break;
            }
            (void) printf("[Camera] Meta: %dx%d fmt=%d stride=%d size=%zu\n", 
                          width, height, (int)context->frametype, stride, bufferSize);
            context->dumpRawCount += 1;
        }
    }
}

static int startApp(dumpFrameContext_t* dumpFrameContext,
                    camera_unit_t cameraUnit,
                    camera_handle_t* cameraHandle,
                    uint32_t* flags)
{
    int             err;
    camera_error_t  cameraErr;

    if ((dumpFrameContext == NULL) || (cameraHandle == NULL) || (flags == NULL)) {
        (void) fprintf(stderr, "NULL parameters\n");
    }

    *flags = (uint32_t) CLEANUP_NONE;

    err = pthread_mutex_init(&dumpFrameContext->mutex, NULL);
    if (err != EOK) {
        (void) fprintf(stderr, "Failed to init mutex: err=%d\n", err);
        return err;
    }
    *flags |= (uint32_t) CLEANUP_MUTEX;

    cameraErr = camera_open(cameraUnit, CAMERA_MODE_RO, cameraHandle);
    if (cameraErr != CAMERA_EOK) {
        (void) fprintf(stderr, "Failed to open the camera\n");
        (void) stopApp(*cameraHandle, dumpFrameContext, *flags);
        return (int) cameraErr;
    }
    *flags |= (uint32_t) CLEANUP_CAMERA_HANDLE;

    cameraErr = camera_get_vf_property(*cameraHandle, CAMERA_IMGPROP_FORMAT, &dumpFrameContext->frametype);
    if (cameraErr != EOK) {
        (void) fprintf(stderr, "Failed to get viewfinder frametype: err=%d\n", cameraErr);
        (void) stopApp(*cameraHandle, dumpFrameContext, *flags);
        return (int) cameraErr;
    }

    cameraErr = camera_start_viewfinder(*cameraHandle, dumpFrame, NULL, (void*)dumpFrameContext);
    if (cameraErr != EOK) {
        (void) fprintf(stderr, "Failed to start viewfinder for camera: err=%d\n", cameraErr);
        (void) stopApp(*cameraHandle, dumpFrameContext, *flags);
        return (int) cameraErr;
    }
    *flags |= (uint32_t) CLEANUP_VIEWFINDER;

    return EOK;
}

int main(int argc, char *argv[])
{
    int                 err = EOK;
    int                 opt;
    uint32_t            flags = (uint32_t) CLEANUP_NONE;
    long                unitLong;
    bool                userPathGiven = false;
    camera_handle_t     cameraHandle = CAMERA_HANDLE_INVALID;
    camera_unit_t       cameraUnit = CAMERA_UNIT_1;
    dumpFrameContext_t  dumpFrameContext = {0};

    while ((opt = getopt(argc, argv, "f:u:")) != -1) {
        switch (opt) {
        case (int) 'f':
            userPathGiven = true;
            err = snprintf(dumpFrameContext.filePath, sizeof(dumpFrameContext.filePath), "%s", optarg);
            if (err < 0) {
                (void) fprintf(stderr, "Failed to get user file path: err=%d\n", errno);
            } else {
                err = EOK;
            }
            break;
        case (int) 'u':
            errno = EOK;
            unitLong = strtol(optarg, NULL, 10);
            if (errno != EOK) {
                (void) fprintf(stderr, "Failed to parse unit argument: err %d\n", errno);
                err = EINVAL;
            } else {
                cameraUnit = (camera_unit_t) unitLong;
            }
            break;
        default:
            break;
        }
    }

    if (err != EOK) {
        return -1;
    }
    if (!userPathGiven) {
        err = snprintf(dumpFrameContext.filePath,
                       sizeof(dumpFrameContext.filePath),
                       "%s",
                       DEFAULT_FILE_PATH);
        if (err < 0) {
            (void) fprintf(stderr, "Failed to copy default path: err=%d\n", errno);
            return -1;
        }
    }

    err = startApp(&dumpFrameContext,
                   cameraUnit,
                   &cameraHandle,
                   &flags);
    if (err != EOK) {
        return -1;
    }

    // Immediately request a raw frame dump
    err = pthread_mutex_lock(&dumpFrameContext.mutex);
    if (err == EOK) {
        dumpFrameContext.dumpType = DUMP_RAW;
        pthread_mutex_unlock(&dumpFrameContext.mutex);
    } else {
        (void) stopApp(cameraHandle, &dumpFrameContext, flags);
        return -1;
    }

    // Wait until the callback captures the frame and increments dumpRawCount
    int timeout_count = 0;
    while (dumpFrameContext.dumpRawCount == 0 && timeout_count < 100) {
        usleep(50000); // 50ms sleep
        timeout_count++;
    }

    if (dumpFrameContext.dumpRawCount == 0) {
        (void) fprintf(stderr, "[Camera] Error: Timeout waiting for camera frame.\n");
        err = ETIMEDOUT;
    }

    // Cleanup on exit
    (void) stopApp(cameraHandle, &dumpFrameContext, flags);

    return (err == EOK) ? 0 : -1;
}
