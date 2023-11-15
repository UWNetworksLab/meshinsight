use proxy_wasm::traits::{Context, HttpContext};
use proxy_wasm::types::{Action, LogLevel};

use prost::Message;
// pb.rs = echo.proto
pub mod echo {
    include!(concat!(env!("OUT_DIR"), "/pb.rs"));
}

#[no_mangle]
pub fn _start() {
    proxy_wasm::set_log_level(LogLevel::Trace);
    proxy_wasm::set_http_context(|context_id, _| -> Box<dyn HttpContext> {
        Box::new(AccessControl { context_id })
    });
}

struct AccessControl {
    #[allow(unused)]
    context_id: u32,
}

impl Context for AccessControl {}

impl HttpContext for AccessControl {
    fn on_http_request_headers(&mut self, _num_of_headers: usize, end_of_stream: bool) -> Action {
        log::warn!("executing on_http_request_headers");
        if !end_of_stream {
            return Action::Continue;
        }

        self.set_http_response_header("content-length", None);
        Action::Continue
    }

    fn on_http_request_body(&mut self, body_size: usize, end_of_stream: bool) -> Action {
        log::warn!("executing on_http_request_body");
        if !end_of_stream {
            // Wait -- we'll be called again when the complete body is buffered
            // at the host side.
            // Returns Continue because there's other filters to process. Return Pause may cause
            // problem in this case.
            // if let Some(body) = self.get_http_request_body(0, body_size) {
            //     log::info!("body: {:?}", body);
            // }
            // return Action::Continue;
            return Action::Pause;
        }

        // Replace the message body if it contains the text "secret".
        // Since we returned "Pause" previuously, this will return the whole body.
        if let Some(body) = self.get_http_request_body(0, body_size) {
            // log::warn!("body: {:?}", body);
            // Parse grpc payload, skip the first 5 bytes
            match echo::Msg::decode(&body[5..]) {
                Ok(req) => {
                    // log::info!("req: {:?}", req);
                    // log::warn!("body.len(): {}", req.body.len());
                    // log::warn!("body : {}", req.body);
                    if req.body == "/test" {
                        // Status code: https://chromium.googlesource.com/external/github.com/grpc/grpc/+/refs/tags/v1.21.4-pre1/doc/statuscodes.md
                        self.send_http_response(
                            // 200,
                            403, // 403 
                            vec![
                                ("grpc-status", "7"),
                                // ("grpc-message", "Access forbidden.\n"),
                            ],
                            None,
                        );
                        return Action::Pause;
                    }
                }
                Err(e) => log::warn!("decode error: {}", e),
            }
        }

        Action::Continue
    }

    fn on_http_response_headers(&mut self, _num_of_headers: usize, end_of_stream: bool) -> Action {
        log::warn!("executing on_http_response_headers");
        Action::Continue
    }


    fn on_http_response_body(&mut self, body_size: usize, end_of_stream: bool) -> Action {
        log::warn!("executing on_http_response_body");

        if let Some(body) = self.get_http_response_body(0, body_size) {
            // log::warn!("body: {:?}", body);
            // Parse grpc payload, skip the first 5 bytes
            match echo::Msg::decode(&body[5..]) {
                Ok(req) => {
                    // log::info!("req: {:?}", req);
                    // log::warn!("body.len(): {}", req.body.len());
                    // log::warn!("body : {}", req.body);
                    if req.body == "/test11" {
                        log::warn!("blocking response");
                        // Status code: https://chromium.googlesource.com/external/github.com/grpc/grpc/+/refs/tags/v1.21.4-pre1/doc/statuscodes.md
                        self.send_http_response(
                            200,
                            // 403, // 403 
                            vec![
                                ("grpc-status", "1"),
                                // ("grpc-message", "Access forbidden.\n"),
                            ],
                            None,
                        );
                        return Action::Pause;
                    }
                }
                Err(e) => log::warn!("decode error: {}", e),
            }
        }

        Action::Continue
    }
    
}
