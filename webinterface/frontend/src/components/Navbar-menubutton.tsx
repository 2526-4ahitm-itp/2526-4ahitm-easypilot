import { Component } from "react";
import { Link } from "react-router-dom";

interface NavbarMenubuttonProps {
    buttonText: string;
    reference: string;
    className?: string;
}

class NavbarMenubutton extends Component<NavbarMenubuttonProps> {
    render() {
        const { buttonText, className, reference } = this.props;

        return (
            <Link className={className} to={reference}>
                {buttonText}
            </Link>
        );
    }
}

export default NavbarMenubutton;
