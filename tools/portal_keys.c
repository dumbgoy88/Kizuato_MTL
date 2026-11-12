/* Send a few emulator keys through the KDE/Wayland RemoteDesktop portal.
 * Build: cc tools/portal_keys.c -o build/portal_keys $(pkg-config --cflags --libs liboeffis-1.0 libei-1.0)
 * The compositor asks the desktop user to allow keyboard control. Commands
 * on stdin: enter, space, up, down, left, right, esc, f12, quit.
 */
#define _POSIX_C_SOURCE 200809L
#include <errno.h>
#include <linux/input-event-codes.h>
#include <poll.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <time.h>
#include <unistd.h>
#include <libei.h>
#include <liboeffis.h>

static int keycode(const char *name)
{
    if (!strcmp(name, "enter")) return KEY_ENTER;
    if (!strcmp(name, "space")) return KEY_SPACE;
    if (!strcmp(name, "up")) return KEY_UP;
    if (!strcmp(name, "down")) return KEY_DOWN;
    if (!strcmp(name, "left")) return KEY_LEFT;
    if (!strcmp(name, "right")) return KEY_RIGHT;
    if (!strcmp(name, "esc")) return KEY_ESC;
    if (!strcmp(name, "f12")) return KEY_F12;
    return -1;
}

static void send_key(struct ei *ei, struct ei_device *kbd, int code)
{
    struct timespec pause = {.tv_sec = 0, .tv_nsec = 50000000};
    ei_device_keyboard_key(kbd, code, true);
    ei_device_frame(kbd, ei_now(ei));
    ei_dispatch(ei);
    nanosleep(&pause, NULL);
    ei_device_keyboard_key(kbd, code, false);
    ei_device_frame(kbd, ei_now(ei));
    ei_dispatch(ei);
}

int main(void)
{
    struct oeffis *portal = oeffis_new(NULL);
    struct ei *ei = NULL;
    struct ei_device *kbd = NULL;
    int keyboard_ready = 0;
    int status = 1;
    if (!portal) return 1;
    setvbuf(stdout, NULL, _IOLBF, 0);
    oeffis_create_session(portal, OEFFIS_DEVICE_KEYBOARD);
    fprintf(stderr, "Waiting for desktop keyboard-control approval...\n");

    for (;;) {
        struct pollfd fds[3] = {
            {.fd = oeffis_get_fd(portal), .events = POLLIN},
            {.fd = ei ? ei_get_fd(ei) : -1, .events = POLLIN},
            {.fd = STDIN_FILENO, .events = POLLIN},
        };
        if (poll(fds, 3, 1000) < 0) {
            if (errno == EINTR) continue;
            perror("poll");
            break;
        }
        if (fds[0].revents & POLLIN) {
            oeffis_dispatch(portal);
            for (;;) {
                enum oeffis_event_type event = oeffis_get_event(portal);
                if (event == OEFFIS_EVENT_NONE) break;
                if (event == OEFFIS_EVENT_CONNECTED_TO_EIS) {
                    int fd = oeffis_get_eis_fd(portal);
                    ei = ei_new_sender(NULL);
                    if (fd < 0 || !ei) {
                        if (fd >= 0) close(fd);
                        fprintf(stderr, "Could not create an input client\n");
                        goto done;
                    }
                    /* ei_setup_backend_fd takes ownership of fd. */
                    if (ei_setup_backend_fd(ei, fd) != 0) {
                        fprintf(stderr, "Could not connect to the compositor input server\n");
                        goto done;
                    }
                    fprintf(stderr, "Portal connected; waiting for keyboard device...\n");
                } else {
                    fprintf(stderr, "Portal closed: %s\n", event == OEFFIS_EVENT_DISCONNECTED
                            ? oeffis_get_error_message(portal) : "desktop session ended");
                    goto done;
                }
            }
        }
        if (ei && fds[1].revents & POLLIN) {
            ei_dispatch(ei);
            struct ei_event *event;
            while ((event = ei_get_event(ei))) {
                enum ei_event_type type = ei_event_get_type(event);
                struct ei_device *device = ei_event_get_device(event);
                if (type == EI_EVENT_SEAT_ADDED)
                    ei_seat_bind_capabilities(ei_event_get_seat(event), EI_DEVICE_CAP_KEYBOARD, NULL);
                else if (type == EI_EVENT_DEVICE_ADDED &&
                         ei_device_has_capability(device, EI_DEVICE_CAP_KEYBOARD))
                    kbd = ei_device_ref(device);
                else if (type == EI_EVENT_DEVICE_RESUMED && device == kbd) {
                    ei_device_start_emulating(kbd, 1);
                    keyboard_ready = 1;
                    puts("ready: enter space up down left right esc f12 quit");
                } else if (type == EI_EVENT_DEVICE_PAUSED && device == kbd)
                    keyboard_ready = 0;
                else if (type == EI_EVENT_DEVICE_REMOVED && device == kbd) {
                    keyboard_ready = 0;
                    kbd = ei_device_unref(kbd);
                } else if (type == EI_EVENT_DISCONNECT) {
                    fprintf(stderr, "Input server disconnected\n");
                    ei_event_unref(event);
                    goto done;
                }
                ei_event_unref(event);
            }
        }
        if (fds[2].revents & POLLIN) {
            char line[80];
            if (!fgets(line, sizeof(line), stdin)) break;
            line[strcspn(line, "\r\n")] = 0;
            if (!strcmp(line, "quit")) { status = 0; break; }
            int code = keycode(line);
            if (code < 0) fprintf(stderr, "Unknown key: %s\n", line);
            else if (!keyboard_ready) fprintf(stderr, "Keyboard not ready\n");
            else { send_key(ei, kbd, code); printf("sent %s\n", line); }
        }
    }
done:
    if (kbd) ei_device_unref(kbd);
    if (ei) ei_unref(ei);
    oeffis_unref(portal);
    return status;
}
