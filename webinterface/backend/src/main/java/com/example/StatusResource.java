package com.example;

import jakarta.ws.rs.GET;
import jakarta.ws.rs.Path;
import jakarta.ws.rs.Produces;
import jakarta.ws.rs.core.MediaType;
import org.eclipse.microprofile.config.inject.ConfigProperty;
import org.jboss.logging.Logger;

/**
 * Health/info endpoint for the EasyPilot companion backend.
 *
 * <p>The heavy lifting (telemetry relay, WebSocket fan-out) lives in the Python
 * relay; this Quarkus service exposes a small, well-defined HTTP surface that a
 * ground station or monitoring probe can poll to confirm the backend is alive
 * and to read its version.
 */
@Path("/api/status")
public class StatusResource {

    private static final Logger LOG = Logger.getLogger(StatusResource.class);

    @ConfigProperty(name = "easypilot.version", defaultValue = "dev")
    String version;

    @GET
    @Produces(MediaType.APPLICATION_JSON)
    public Status status() {
        LOG.debug("Status endpoint queried");
        return new Status("easypilot-backend", "UP", version);
    }

    /** Immutable status payload serialized to JSON. */
    public record Status(String name, String status, String version) {
    }
}
