import { Component } from "react";
import NavbarMenubutton from "./Navbar-menubutton";

class Navbar extends Component {
    render() {
        return (
            <div className="primary-basic flex gap-10 w-1/2 p-4">
                <NavbarMenubutton
                    className="text-2xl"
                    buttonText="Simulator"
                    reference="/simulator"
                />
                <NavbarMenubutton
                    className="text-2xl"
                    buttonText="Docs"
                    reference="/docs"
                />
            </div>
        );
    }
}

export default Navbar;
